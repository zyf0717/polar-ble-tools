from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from polar_ble_tools.ble.transport import BleTransport
from polar_ble_tools.device import PolarDeviceTarget, resolve_polar_device_target
from polar_ble_tools.passive_data.collector import (
    ExistingFilePolicy,
    PassiveCleanupResult,
    PassiveCollectionResult,
    PassiveFileCollector,
    normalize_existing_file_policy,
)
from polar_ble_tools.passive_data.storage import PassiveFileStore
from polar_ble_tools.polar.offline import OfflineRecordingEntry
from polar_ble_tools.polar.passive import (
    PassiveDomain,
    PassiveFileListing,
    normalize_passive_domain,
)
from polar_ble_tools.raw_data.collector import (
    CleanupResult,
    CollectionRecordResult,
    CollectionResult,
    RawRecordingCollector,
)
from polar_ble_tools.raw_data.storage import RawRecordingStore
from polar_ble_tools.workflows import DeviceWorkflowRunner


@dataclass(frozen=True)
class RawCollectionResult:
    device_id: str
    store_root: str
    output_dir: str
    manifest_path: str
    listed: int
    fetched: int
    skipped: int
    ignored: int
    failed: int
    records: list[CollectionRecordResult]
    deleted: int = 0
    delete_failed: int = 0

    @property
    def ok(self) -> bool:
        return self.failed == 0 and self.delete_failed == 0

    def to_jsonable(self) -> dict[str, object]:
        return {
            **self.__dict__,
            "records": [record.to_jsonable() for record in self.records],
        }


async def collect_raw_recordings(
    target: PolarDeviceTarget | str,
    *,
    root: str | Path,
    device_id: str | None = None,
    record_types: set[str] | None = None,
    delete_after_collect: bool = False,
    transport_factory: Callable[[], BleTransport] | None = None,
) -> RawCollectionResult:
    resolved = resolve_polar_device_target(target)
    effective_id = device_id or resolved.device_id
    if effective_id is None:  # pragma: no cover - normalization invariant
        raise ValueError("Resolved device target is missing device_id.")
    store = RawRecordingStore(root)

    async def workflow(device):
        return await RawRecordingCollector(device.services.offline, store).collect(
            effective_id,
            record_types=set(record_types) if record_types else None,
            delete_after_collect=delete_after_collect,
            control_client=device.services.offline_control if delete_after_collect else None,
        )

    result: CollectionResult = await DeviceWorkflowRunner(transport_factory=transport_factory).run(
        resolved, workflow
    )
    return _raw_collection_result(result, store, effective_id)


async def list_raw_recordings(
    target: PolarDeviceTarget | str,
    *,
    transport_factory: Callable[[], BleTransport] | None = None,
) -> list[OfflineRecordingEntry]:
    resolved = resolve_polar_device_target(target)

    async def workflow(device):
        return await device.services.offline.list_recording_files()

    return await DeviceWorkflowRunner(transport_factory=transport_factory).run(resolved, workflow)


async def cleanup_raw_recordings(
    target: PolarDeviceTarget | str,
    *,
    root: str | Path,
    record_types: set[str] | None = None,
    delete_all: bool = False,
    dry_run: bool = False,
    transport_factory: Callable[[], BleTransport] | None = None,
) -> CleanupResult:
    resolved = resolve_polar_device_target(target)
    if resolved.device_id is None:  # pragma: no cover - normalization invariant
        raise ValueError("Resolved device target is missing device_id.")
    store = RawRecordingStore(root)

    async def workflow(device):
        return await RawRecordingCollector(device.services.offline, store).cleanup(
            resolved.device_id,
            record_types=set(record_types) if record_types else None,
            delete_all=delete_all,
            dry_run=dry_run,
            control_client=device.services.offline_control,
        )

    return await DeviceWorkflowRunner(transport_factory=transport_factory).run(resolved, workflow)


async def list_passive_files(
    target: PolarDeviceTarget | str,
    *,
    domains: tuple[PassiveDomain, ...],
    from_date,
    to_date,
    transport_factory: Callable[[], BleTransport] | None = None,
) -> PassiveFileListing:
    resolved = resolve_polar_device_target(target)

    async def workflow(device):
        async with device.services.passive.sync_session():
            return await device.services.passive.list_files(
                domains, from_date=from_date, to_date=to_date
            )

    return await DeviceWorkflowRunner(transport_factory=transport_factory).run(resolved, workflow)


async def collect_passive_files(
    target: PolarDeviceTarget | str,
    *,
    domains: tuple[PassiveDomain, ...],
    from_date,
    to_date,
    root: str | Path,
    device_id: str | None = None,
    existing_file_policy: ExistingFilePolicy | str = ExistingFilePolicy.SKIP,
    delete_after_collect: bool = False,
    transport_factory: Callable[[], BleTransport] | None = None,
) -> PassiveCollectionResult:
    resolved = resolve_polar_device_target(target)
    effective_id = device_id or resolved.device_id
    if effective_id is None:  # pragma: no cover - normalization invariant
        raise ValueError("Resolved device target is missing device_id.")
    policy = normalize_existing_file_policy(existing_file_policy)
    store = PassiveFileStore(root)

    async def workflow(device):
        async with device.services.passive.sync_session():
            return await PassiveFileCollector(device.services.passive, store).collect(
                effective_id,
                domains,
                from_date=from_date,
                to_date=to_date,
                existing_file_policy=policy,
                delete_after_collect=delete_after_collect,
            )

    return await DeviceWorkflowRunner(transport_factory=transport_factory).run(resolved, workflow)


async def cleanup_passive_files(
    target: PolarDeviceTarget | str,
    *,
    root: str | Path,
    domain: PassiveDomain | str,
    delete_through,
    dry_run: bool = False,
    transport_factory: Callable[[], BleTransport] | None = None,
) -> PassiveCleanupResult:
    normalized_domain = normalize_passive_domain(domain)
    if delete_through >= date.today():
        raise ValueError("delete_through must be earlier than the current local date.")
    resolved = resolve_polar_device_target(target)
    device_id = resolved.device_id
    if device_id is None:  # pragma: no cover
        raise ValueError("Resolved device target is missing device_id.")
    store = PassiveFileStore(root)
    if dry_run:
        return await PassiveFileCollector(None, store).cleanup(  # type: ignore[arg-type]
            device_id, domain=normalized_domain, delete_through=delete_through, dry_run=True
        )

    async def workflow(device):
        async with device.services.passive.sync_session():
            return await PassiveFileCollector(device.services.passive, store).cleanup(
                device_id, domain=normalized_domain, delete_through=delete_through, dry_run=False
            )

    return await DeviceWorkflowRunner(transport_factory=transport_factory).run(resolved, workflow)


def _raw_collection_result(
    result: CollectionResult, store: RawRecordingStore, device_id: str
) -> RawCollectionResult:
    manifest_path = store.manifest_path(device_id)
    return RawCollectionResult(
        device_id=device_id,
        store_root=str(store.root),
        output_dir=str(manifest_path.parent),
        manifest_path=str(manifest_path),
        listed=result.listed,
        fetched=result.fetched,
        skipped=result.skipped,
        ignored=result.ignored,
        failed=result.failed,
        records=result.records,
        deleted=result.deleted,
        delete_failed=result.delete_failed,
    )
