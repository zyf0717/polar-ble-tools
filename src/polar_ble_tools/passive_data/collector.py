from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from uuid import uuid4

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
    logical_date: str | None = None
    delete_status: str | None = None
    delete_error: str | None = None

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
    deleted: int = 0
    delete_failed: int = 0

    @property
    def ok(self) -> bool:
        return self.failed == 0

    def to_jsonable(self) -> dict[str, object]:
        return {**self.__dict__, "records": [record.to_jsonable() for record in self.records]}


@dataclass(frozen=True)
class PassiveCleanupResult:
    device_id: str
    domain: str
    selected: int
    deleted: int
    dry_run: int
    blocked: int
    failed: int
    records: list[PassiveCollectionRecordResult]

    @property
    def ok(self) -> bool:
        return self.blocked == 0 and self.failed == 0

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
        delete_after_collect: bool = False,
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
        if delete_after_collect and not any(record.status == "failed" for record in records):
            records = await self._delete_after_collect(device_id, listing.entries, records)
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
            deleted=sum(record.delete_status == "deleted" for record in records),
            delete_failed=sum(
                record.delete_status in {"blocked_unverified", "failed"} for record in records
            ),
        )

    async def _delete_after_collect(
        self,
        device_id: str,
        entries: list[PassiveFileEntry],
        records: list[PassiveCollectionRecordResult],
    ) -> list[PassiveCollectionRecordResult]:
        by_path = {entry.path: entry for entry in entries}
        eligible = [
            record
            for record in records
            if record.status in {"fetched", "skipped"} and record.logical_date is not None
        ]
        if not eligible:
            return records
        latest_date = max(record.logical_date for record in eligible)
        operation_id = str(uuid4())
        outcomes: dict[str, tuple[str, str | None]] = {}
        for record in eligible:
            if record.logical_date == latest_date:
                continue
            entry = by_path[record.device_path]
            verified = self.store.verify_existing_file(
                device_id,
                device_path=entry.path,
                device_size=entry.size,
                domain=entry.domain.value,
            )
            if verified is None:
                status, error = "blocked_unverified", "local verification failed"
                deleted_paths: tuple[str, ...] = ()
            else:
                try:
                    await self.client.remove_file(entry)
                except Exception as exc:
                    if isinstance(exc, BleTransportError):
                        raise
                    status, error, deleted_paths = "failed", str(exc), ()
                else:
                    status, error, deleted_paths = "deleted", None, (entry.path,)
            self.store.append_deletion_audit(
                device_id,
                operation_id=operation_id,
                domain=entry.domain.value,
                logical_date=record.logical_date,
                device_path=entry.path,
                local_path=record.local_path,
                local_sha256=record.sha256,
                status=status,
                deleted_paths=deleted_paths,
                error=error,
            )
            outcomes[entry.path] = (status, error)
        return [
            record
            if record.device_path not in outcomes
            else PassiveCollectionRecordResult(
                **{
                    **record.__dict__,
                    "delete_status": outcomes[record.device_path][0],
                    "delete_error": outcomes[record.device_path][1],
                }
            )
            for record in records
        ]

    async def cleanup(
        self,
        device_id: str,
        *,
        domain: PassiveDomain,
        delete_through: date,
        dry_run: bool,
    ) -> PassiveCleanupResult:
        latest = {
            entry.device_path: entry
            for entry in self.store.read_manifest(device_id)
            if entry.domain == domain.value
        }
        unknown_date_paths = sorted(
            entry.device_path for entry in latest.values() if entry.logical_date is None
        )
        if unknown_date_paths:
            raise ValueError(
                "Passive cleanup does not support records with unknown logical dates: "
                + ", ".join(unknown_date_paths)
            )
        selected = sorted(
            (
                entry
                for entry in latest.values()
                if entry.logical_date is not None
                and entry.logical_date <= delete_through.isoformat()
            ),
            key=lambda entry: (entry.logical_date or "", entry.device_path),
        )
        operation_id = str(uuid4())
        records: list[PassiveCollectionRecordResult] = []
        for manifest in selected:
            entry = PassiveFileEntry(
                domain,
                manifest.device_path,
                manifest.device_size,
                date.fromisoformat(manifest.logical_date),
            )
            verified = self.store.verify_existing_file(
                device_id,
                device_path=entry.path,
                device_size=entry.size,
                domain=domain.value,
            )
            if verified is None:
                status, error, deleted_paths = "blocked_unverified", "local verification failed", ()
            elif dry_run:
                status, error, deleted_paths = "dry_run", None, ()
            else:
                try:
                    await self.client.remove_file(entry)
                except Exception as exc:
                    if isinstance(exc, BleTransportError):
                        raise
                    status, error, deleted_paths = "failed", str(exc), ()
                else:
                    status, error, deleted_paths = "deleted", None, (entry.path,)
            self.store.append_deletion_audit(
                device_id,
                operation_id=operation_id,
                domain=domain.value,
                logical_date=manifest.logical_date,
                device_path=entry.path,
                local_path=manifest.local_path,
                local_sha256=manifest.sha256,
                status=status,
                deleted_paths=deleted_paths,
                error=error,
                dry_run=dry_run,
            )
            records.append(
                PassiveCollectionRecordResult(
                    entry.path,
                    domain.value,
                    "skipped",
                    manifest.local_path,
                    manifest.fetched_size,
                    manifest.sha256,
                    logical_date=manifest.logical_date,
                    delete_status=status,
                    delete_error=error,
                )
            )
        return PassiveCleanupResult(
            device_id,
            domain.value,
            len(selected),
            sum(record.delete_status == "deleted" for record in records),
            sum(record.delete_status == "dry_run" for record in records),
            sum(record.delete_status == "blocked_unverified" for record in records),
            sum(record.delete_status == "failed" for record in records),
            records,
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
        logical_date=entry.logical_date.isoformat() if entry.logical_date else None,
    )
