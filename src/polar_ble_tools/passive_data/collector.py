from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from polar_ble_tools.ble.transport import BleTransportError
from polar_ble_tools.passive_data.storage import PassiveFileManifestEntry, PassiveFileStore
from polar_ble_tools.polar.passive import PassiveDataClient, PassiveDomain, PassiveFileEntry


class ExistingFilePolicy(StrEnum):
    SKIP = "skip"
    OVERWRITE = "overwrite"


def normalize_existing_file_policy(raw: ExistingFilePolicy | str) -> ExistingFilePolicy:
    if isinstance(raw, ExistingFilePolicy):
        return raw
    try:
        return ExistingFilePolicy(raw.strip().lower())
    except ValueError as exc:
        raise ValueError("existing_file_policy must be 'skip' or 'overwrite'.") from exc


@dataclass(frozen=True)
class PassiveCollectionRecordResult:
    device_path: str
    domain: str
    status: str
    local_path: str | None = None
    fetched_size: int | None = None
    sha256: str | None = None
    error: str | None = None

    def to_jsonable(self) -> dict[str, object]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class PassiveCollectionResult:
    device_id: str
    output_dir: str
    manifest_path: str
    listed: int
    fetched: int
    skipped: int
    failed: int
    missing: list[str]
    records: list[PassiveCollectionRecordResult]

    @property
    def ok(self) -> bool:
        return self.failed == 0

    def to_jsonable(self) -> dict[str, object]:
        return {**self.__dict__, "records": [record.to_jsonable() for record in self.records]}


class PassiveFileCollector:
    def __init__(self, client: PassiveDataClient, store: PassiveFileStore) -> None:
        self.client = client
        self.store = store

    async def collect(
        self,
        device_id: str,
        domains: tuple[PassiveDomain, ...],
        *,
        from_date: date,
        to_date: date,
        existing_file_policy: ExistingFilePolicy | str = ExistingFilePolicy.SKIP,
    ) -> PassiveCollectionResult:
        policy = normalize_existing_file_policy(existing_file_policy)
        listing = await self.client.list_files(domains, from_date=from_date, to_date=to_date)
        records: list[PassiveCollectionRecordResult] = []
        for entry in listing.entries:
            existing = self.store.verify_existing_file(
                device_id, device_path=entry.path, device_size=entry.size
            )
            if policy == ExistingFilePolicy.SKIP and existing is not None:
                records.append(_stored_result(entry, "skipped", existing))
                continue
            try:
                payload = await self.client.fetch_raw_file(entry)
                persisted = self.store.persist_file(
                    device_id,
                    domain=entry.domain.value,
                    device_path=entry.path,
                    device_size=entry.size,
                    payload=payload,
                    logical_date=entry.logical_date.isoformat() if entry.logical_date else None,
                )
            except Exception as exc:
                if isinstance(exc, BleTransportError):
                    raise
                records.append(
                    PassiveCollectionRecordResult(
                        entry.path, entry.domain.value, "failed", error=str(exc)
                    )
                )
                continue
            records.append(_stored_result(entry, "fetched", persisted))
        return PassiveCollectionResult(
            device_id=device_id,
            output_dir=str(self.store.root),
            manifest_path=str(self.store.manifest_path(device_id)),
            listed=len(listing.entries),
            fetched=sum(record.status == "fetched" for record in records),
            skipped=sum(record.status == "skipped" for record in records),
            failed=sum(record.status == "failed" for record in records),
            missing=listing.missing,
            records=records,
        )


def _stored_result(
    entry: PassiveFileEntry, status: str, manifest: PassiveFileManifestEntry
) -> PassiveCollectionRecordResult:
    return PassiveCollectionRecordResult(
        entry.path,
        entry.domain.value,
        status,
        manifest.local_path,
        manifest.fetched_size,
        manifest.sha256,
    )
