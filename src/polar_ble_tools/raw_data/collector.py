from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from polar_ble_tools.ble.transport import BleTransportError
from polar_ble_tools.polar.offline import (
    DeviceDeletionResult,
    DeviceDeletionStatus,
    OfflineRecordingClient,
    OfflineRecordingControlClient,
    OfflineRecordingEntry,
    base_record_type_for,
    record_type_matches_filter,
)
from polar_ble_tools.polar.pmd import PolarDeviceDataType
from polar_ble_tools.raw_data.storage import (
    DEFAULT_RAW_ROOT,
    RawRecordingManifestEntry,
    RawRecordingStore,
)


class RawCollectionStatus(StrEnum):
    FETCHED = "fetched"
    SKIPPED = "skipped"
    IGNORED = "ignored"
    FAILED = "failed"


@dataclass(frozen=True)
class CollectionRecordResult:
    device_path: str
    record_type: str
    status: RawCollectionStatus
    base_record_type: str | None = None
    local_path: str | None = None
    fetched_size: int | None = None
    sha256: str | None = None
    error: str | None = None
    delete_status: DeviceDeletionStatus | None = None
    deleted_paths: tuple[str, ...] | None = None
    cleaned_directories: tuple[str, ...] | None = None
    delete_error: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", RawCollectionStatus(self.status))
        if self.delete_status is not None:
            object.__setattr__(self, "delete_status", DeviceDeletionStatus(self.delete_status))
        if self.deleted_paths is not None:
            object.__setattr__(self, "deleted_paths", tuple(self.deleted_paths))
        if self.cleaned_directories is not None:
            object.__setattr__(self, "cleaned_directories", tuple(self.cleaned_directories))

    def to_jsonable(self) -> dict[str, object]:
        return {
            **self.__dict__,
            "status": self.status.value,
            "delete_status": self.delete_status.value if self.delete_status else None,
            "deleted_paths": list(self.deleted_paths) if self.deleted_paths is not None else None,
            "cleaned_directories": (
                list(self.cleaned_directories) if self.cleaned_directories is not None else None
            ),
        }

    def with_delete_result(self, result: DeviceDeletionResult) -> CollectionRecordResult:
        return CollectionRecordResult(
            **{
                **self.__dict__,
                "delete_status": result.status,
                "deleted_paths": result.deleted_paths,
                "cleaned_directories": result.cleaned_directories,
                "delete_error": result.error,
            }
        )


@dataclass(frozen=True)
class CollectionResult:
    device_id: str
    output_dir: str
    listed: int
    fetched: int
    skipped: int
    ignored: int
    failed: int
    records: tuple[CollectionRecordResult, ...]
    deleted: int = 0
    delete_failed: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "records", tuple(self.records))

    @property
    def ok(self) -> bool:
        return self.failed == 0 and self.delete_failed == 0

    def to_jsonable(self) -> dict[str, object]:
        return {
            **self.__dict__,
            "records": [record.to_jsonable() for record in self.records],
        }


@dataclass(frozen=True)
class CleanupResult:
    device_id: str
    output_dir: str
    listed: int
    selected: int
    deleted: int
    dry_run: int
    blocked: int
    failed: int
    records: tuple[DeviceDeletionResult, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "records", tuple(self.records))

    @property
    def ok(self) -> bool:
        return self.blocked == 0 and self.failed == 0

    def to_jsonable(self) -> dict[str, object]:
        return {
            **self.__dict__,
            "records": [record.to_jsonable() for record in self.records],
        }


class RawRecordingCollector:
    def __init__(self, offline_client: OfflineRecordingClient, store: RawRecordingStore) -> None:
        self.offline_client = offline_client
        self.store = store

    async def collect(
        self,
        device_id: str,
        *,
        record_types: set[str] | None = None,
        delete_after_collect: bool = False,
        control_client: OfflineRecordingControlClient | None = None,
    ) -> CollectionResult:
        requested = {value.upper() for value in record_types} if record_types else None
        entries = await self.offline_client.list_recording_files()
        results: list[CollectionRecordResult] = []
        for entry in entries:
            if requested and not any(
                record_type_matches_filter(entry.record_type, value) for value in requested
            ):
                results.append(self._result(entry, status=RawCollectionStatus.IGNORED))
                continue
            existing = self.store.has_existing_record(device_id, entry)
            if existing is not None:
                results.append(self._skipped_result(entry.path, existing))
                continue
            try:
                record = await self.offline_client.fetch_record(entry)
                results.append(
                    self._fetched_result(
                        self.store.persist_record(device_id, entry, record.payload)
                    )
                )
            except Exception as exc:
                if isinstance(exc, BleTransportError):
                    raise
                results.append(
                    self._result(entry, status=RawCollectionStatus.FAILED, error=str(exc))
                )

        if delete_after_collect:
            eligible = {
                result.device_path
                for result in results
                if result.status in {RawCollectionStatus.FETCHED, RawCollectionStatus.SKIPPED}
            }
            deletions = await self._delete_verified_records(
                device_id,
                [entry for entry in entries if entry.path in eligible],
                eligible_paths=eligible,
                dry_run=False,
                control_client=control_client,
            )
            results = self._attach_deletions(results, deletions)
        return CollectionResult(
            device_id=device_id,
            output_dir=str(self.store.root),
            listed=len(entries),
            fetched=sum(item.status == RawCollectionStatus.FETCHED for item in results),
            skipped=sum(item.status == RawCollectionStatus.SKIPPED for item in results),
            ignored=sum(item.status == RawCollectionStatus.IGNORED for item in results),
            failed=sum(item.status == RawCollectionStatus.FAILED for item in results),
            records=tuple(results),
            deleted=sum(item.delete_status == DeviceDeletionStatus.DELETED for item in results),
            delete_failed=sum(
                item.delete_status
                in {
                    DeviceDeletionStatus.BLOCKED_UNVERIFIED,
                    DeviceDeletionStatus.BLOCKED_ACTIVE,
                    DeviceDeletionStatus.FAILED,
                }
                for item in results
            ),
        )

    async def cleanup(
        self,
        device_id: str,
        *,
        record_types: set[str] | None = None,
        delete_all: bool = False,
        dry_run: bool = False,
        control_client: OfflineRecordingControlClient | None = None,
    ) -> CleanupResult:
        if delete_all == bool(record_types):
            raise ValueError("cleanup requires exactly one of delete_all or record_types.")
        requested = {value.upper() for value in record_types} if record_types else None
        entries = await self.offline_client.list_recording_files()
        selected = [
            entry
            for entry in entries
            if delete_all
            or (
                requested is not None
                and any(record_type_matches_filter(entry.record_type, value) for value in requested)
            )
        ]
        results = await self._delete_verified_records(
            device_id,
            selected,
            eligible_paths={entry.path for entry in selected},
            dry_run=dry_run,
            control_client=control_client,
        )
        return CleanupResult(
            device_id=device_id,
            output_dir=str(self.store.root),
            listed=len(entries),
            selected=len(selected),
            deleted=sum(item.status == DeviceDeletionStatus.DELETED for item in results),
            dry_run=sum(item.status == DeviceDeletionStatus.DRY_RUN for item in results),
            blocked=sum(
                item.status
                in {
                    DeviceDeletionStatus.BLOCKED_UNVERIFIED,
                    DeviceDeletionStatus.BLOCKED_ACTIVE,
                }
                for item in results
            ),
            failed=sum(item.status == DeviceDeletionStatus.FAILED for item in results),
            records=tuple(results),
        )

    async def _delete_verified_records(
        self,
        device_id: str,
        entries: list[OfflineRecordingEntry],
        *,
        eligible_paths: set[str],
        dry_run: bool,
        control_client: OfflineRecordingControlClient | None,
    ) -> list[DeviceDeletionResult]:
        active_status: dict[PolarDeviceDataType, bool] = {}
        active_error: str | None = None
        if not dry_run:
            if control_client is None:
                active_error = "active recording status client is required"
            else:
                try:
                    active_status = await control_client.get_recording_status()
                except BleTransportError:
                    raise
                except Exception as exc:
                    active_error = f"active recording status unavailable: {exc}"
        results: list[DeviceDeletionResult] = []
        processed: set[str] = set()
        for entry in sorted(entries, key=lambda item: item.path):
            if entry.path in processed:
                continue
            try:
                family = await self.offline_client.list_record_family(entry)
            except Exception as exc:
                if isinstance(exc, BleTransportError):
                    raise
                results.append(
                    self._audit(
                        device_id,
                        self._deletion(
                            entry,
                            DeviceDeletionStatus.FAILED,
                            [entry.path],
                            str(exc),
                        ),
                    )
                )
                continue
            paths = [item.path for item in family]
            processed.update(paths)
            if set(paths) - eligible_paths:
                results.append(
                    self._audit(
                        device_id,
                        self._deletion(
                            entry,
                            DeviceDeletionStatus.BLOCKED_UNVERIFIED,
                            paths,
                            "record family has unselected members",
                        ),
                    )
                )
                continue
            unverified = [
                item.path
                for item in family
                if self.store.verify_existing_record(device_id, item) is None
            ]
            if unverified:
                results.append(
                    self._audit(
                        device_id,
                        self._deletion(
                            entry,
                            DeviceDeletionStatus.BLOCKED_UNVERIFIED,
                            paths,
                            "local verification failed: " + ", ".join(unverified),
                        ),
                    )
                )
                continue
            if active_error:
                results.append(
                    self._audit(
                        device_id,
                        self._deletion(
                            entry, DeviceDeletionStatus.BLOCKED_ACTIVE, paths, active_error
                        ),
                    )
                )
                continue
            active_types = sorted(
                {
                    base
                    for item in family
                    if (base := base_record_type_for(item.record_type))
                    and active_status.get(PolarDeviceDataType(base), False)
                }
            )
            if active_types:
                results.append(
                    self._audit(
                        device_id,
                        self._deletion(
                            entry,
                            DeviceDeletionStatus.BLOCKED_ACTIVE,
                            paths,
                            "offline recording is active for types: " + ", ".join(active_types),
                        ),
                    )
                )
                continue
            try:
                deletion = await self.offline_client.remove_record(entry, dry_run=dry_run)
            except BleTransportError as exc:
                self._audit(
                    device_id,
                    self._deletion(entry, DeviceDeletionStatus.FAILED, paths, str(exc)),
                )
                raise
            results.append(self._audit(device_id, deletion))
        return results

    def _audit(self, device_id: str, result: DeviceDeletionResult) -> DeviceDeletionResult:
        self.store.append_deletion_result(device_id, result)
        return result

    @staticmethod
    def _result(
        entry: OfflineRecordingEntry,
        *,
        status: RawCollectionStatus,
        error: str | None = None,
    ) -> CollectionRecordResult:
        return CollectionRecordResult(
            entry.path,
            entry.record_type,
            status,
            base_record_type_for(entry.record_type),
            error=error,
        )

    @staticmethod
    def _deletion(
        entry: OfflineRecordingEntry,
        status: DeviceDeletionStatus,
        paths: list[str],
        error: str | None = None,
    ) -> DeviceDeletionResult:
        return DeviceDeletionResult(
            entry.path,
            entry.record_type,
            base_record_type_for(entry.record_type),
            status,
            tuple(paths),
            (),
            error,
        )

    @staticmethod
    def _fetched_result(entry: RawRecordingManifestEntry) -> CollectionRecordResult:
        return CollectionRecordResult(
            entry.device_path,
            entry.record_type,
            RawCollectionStatus.FETCHED,
            base_record_type_for(entry.record_type),
            entry.local_path,
            entry.fetched_size,
            entry.sha256,
        )

    @staticmethod
    def _skipped_result(path: str, entry: RawRecordingManifestEntry) -> CollectionRecordResult:
        return CollectionRecordResult(
            path,
            entry.record_type,
            RawCollectionStatus.SKIPPED,
            base_record_type_for(entry.record_type),
            entry.local_path,
            entry.fetched_size,
            entry.sha256,
        )

    @staticmethod
    def _attach_deletions(
        records: list[CollectionRecordResult], deletions: list[DeviceDeletionResult]
    ) -> list[CollectionRecordResult]:
        by_path = {path: result for result in deletions for path in result.deleted_paths}
        return [
            record.with_delete_result(by_path[record.device_path])
            if record.device_path in by_path
            else record
            for record in records
        ]


def raw_recording_store(root: str | Path = DEFAULT_RAW_ROOT) -> RawRecordingStore:
    return RawRecordingStore(root)
