from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from polar_ble_tools.polar.offline import DeviceDeletionResult, OfflineRecordingEntry
from polar_ble_tools.storage_utils import append_json_line, atomic_write_bytes

SCHEMA_VERSION = 1
DEFAULT_RAW_ROOT = Path(".local/polar-ble-raw")
MANIFEST_FILENAME = "manifest.jsonl"
DELETION_AUDIT_FILENAME = "device-deletions.jsonl"
DEVICE_ID_RE = re.compile(r"[^A-Za-z0-9]+")
RECORDING_PATH_RE = re.compile(
    r"^/U/(?P<user>\d+)/(?P<date>\d{8})/R/(?P<time>\d{6})/(?P<filename>[^/]+\.REC)$",
    re.IGNORECASE,
)


class RawRecordingStoreError(RuntimeError):
    """Raised when raw-recording storage cannot verify its local state."""


@dataclass(frozen=True)
class RawRecordingManifestEntry:
    schema_version: int
    device_id: str
    device_path: str
    local_path: str
    record_type: str
    device_user_index: int
    started_at: str | None
    device_size: int
    fetched_size: int
    sha256: str
    fetched_at: str
    status: str

    @classmethod
    def from_jsonable(cls, raw: dict[str, Any]) -> RawRecordingManifestEntry:
        return cls(
            schema_version=int(raw["schema_version"]),
            device_id=str(raw["device_id"]),
            device_path=str(raw["device_path"]),
            local_path=str(raw["local_path"]),
            record_type=str(raw["record_type"]),
            device_user_index=int(raw["device_user_index"]),
            started_at=str(raw["started_at"]) if raw["started_at"] is not None else None,
            device_size=int(raw["device_size"]),
            fetched_size=int(raw["fetched_size"]),
            sha256=str(raw["sha256"]),
            fetched_at=str(raw["fetched_at"]),
            status=str(raw["status"]),
        )

    def to_jsonable(self) -> dict[str, object]:
        return {
            "device_id": self.device_id,
            "device_path": self.device_path,
            "device_size": self.device_size,
            "device_user_index": self.device_user_index,
            "fetched_at": self.fetched_at,
            "fetched_size": self.fetched_size,
            "local_path": self.local_path,
            "record_type": self.record_type,
            "schema_version": self.schema_version,
            "sha256": self.sha256,
            "started_at": self.started_at,
            "status": self.status,
        }


class RawRecordingStore:
    def __init__(self, root: str | Path = DEFAULT_RAW_ROOT) -> None:
        self.root = Path(root)

    def sanitize_device_id(self, device_id: str) -> str:
        sanitized = DEVICE_ID_RE.sub("", device_id).upper()
        if not sanitized:
            raise RawRecordingStoreError("Device id does not contain alphanumeric characters.")
        return sanitized

    def manifest_path(self, device_id: str) -> Path:
        return self.root / self.sanitize_device_id(device_id) / MANIFEST_FILENAME

    def deletion_audit_path(self, device_id: str) -> Path:
        return self.root / self.sanitize_device_id(device_id) / DELETION_AUDIT_FILENAME

    def local_record_path(self, device_id: str, entry: OfflineRecordingEntry) -> Path:
        user_index, date_text, time_text, record_type = self._path_parts(entry.path)
        return (
            self.root
            / self.sanitize_device_id(device_id)
            / f"U{user_index}"
            / date_text
            / time_text
            / f"{record_type}.REC"
        )

    def read_manifest(self, device_id: str) -> list[RawRecordingManifestEntry]:
        path = self.manifest_path(device_id)
        if not path.exists():
            return []
        entries: list[RawRecordingManifestEntry] = []
        raw_lines = path.read_bytes().split(b"\n")
        # A crash can leave only the final append torn.  Earlier complete JSONL
        # rows remain authoritative; the next append starts a fresh row.
        if raw_lines and raw_lines[-1]:
            raw_lines.pop()
        for line_number, raw_line in enumerate(raw_lines, 1):
            if not raw_line.strip():
                continue
            try:
                line = raw_line.decode("utf-8")
                entries.append(RawRecordingManifestEntry.from_jsonable(json.loads(line)))
            except (
                UnicodeDecodeError,
                KeyError,
                TypeError,
                ValueError,
                json.JSONDecodeError,
            ) as exc:
                raise RawRecordingStoreError(
                    f"Invalid manifest entry at {path}:{line_number}."
                ) from exc
        return entries

    def persist_record(
        self,
        device_id: str,
        entry: OfflineRecordingEntry,
        payload: bytes,
        *,
        fetched_at: datetime | None = None,
    ) -> RawRecordingManifestEntry:
        if len(payload) != entry.size:
            raise RawRecordingStoreError(
                f"Fetched byte count for {entry.path} does not match device directory size."
            )
        final_path = self.local_record_path(device_id, entry)
        self._atomic_write_bytes(final_path, payload)
        manifest_entry = RawRecordingManifestEntry(
            schema_version=SCHEMA_VERSION,
            device_id=self.sanitize_device_id(device_id),
            device_path=entry.path,
            local_path=final_path.relative_to(self.root).as_posix(),
            record_type=entry.record_type,
            device_user_index=entry.user_index,
            started_at=entry.started_at.isoformat() if entry.started_at else None,
            device_size=entry.size,
            fetched_size=len(payload),
            sha256=hashlib.sha256(payload).hexdigest(),
            fetched_at=(fetched_at or datetime.now(UTC))
            .astimezone(UTC)
            .isoformat()
            .replace("+00:00", "Z"),
            status="fetched",
        )
        self._append_manifest(device_id, manifest_entry)
        return manifest_entry

    def verify_existing_record(
        self, device_id: str, entry: OfflineRecordingEntry
    ) -> RawRecordingManifestEntry | None:
        sanitized = self.sanitize_device_id(device_id)
        for manifest_entry in reversed(self.read_manifest(device_id)):
            if (
                manifest_entry.schema_version != SCHEMA_VERSION
                or manifest_entry.device_id != sanitized
                or manifest_entry.device_path != entry.path
                or manifest_entry.status != "fetched"
                or manifest_entry.device_size != entry.size
                or manifest_entry.fetched_size != entry.size
            ):
                continue
            local_path = self.resolve_local_path(manifest_entry.local_path)
            if not local_path.exists() or local_path.stat().st_size != entry.size:
                continue
            if hashlib.sha256(local_path.read_bytes()).hexdigest() == manifest_entry.sha256:
                return manifest_entry
        return None

    def has_existing_record(
        self, device_id: str, entry: OfflineRecordingEntry
    ) -> RawRecordingManifestEntry | None:
        """Return only a complete, hash-verified prior retrieval.

        Collection must never treat a same-sized but corrupt local file as a safe
        duplicate, particularly before a later device deletion operation.
        """
        return self.verify_existing_record(device_id, entry)

    def append_deletion_result(
        self,
        device_id: str,
        result: DeviceDeletionResult,
        *,
        deleted_at: datetime | None = None,
    ) -> None:
        timestamp = (deleted_at or datetime.now(UTC)).astimezone(UTC)
        self._append_json_line(
            self.deletion_audit_path(device_id),
            {
                **result.to_jsonable(),
                "deleted_at": timestamp.isoformat().replace("+00:00", "Z"),
                "device_id": self.sanitize_device_id(device_id),
                "schema_version": SCHEMA_VERSION,
            },
        )

    def _append_manifest(self, device_id: str, manifest_entry: RawRecordingManifestEntry) -> None:
        self._append_json_line(self.manifest_path(device_id), manifest_entry.to_jsonable())

    def _append_json_line(self, path: Path, value: dict[str, object]) -> None:
        append_json_line(path, value)

    def resolve_local_path(self, stored_path: str) -> Path:
        """Resolve v1 absolute entries and root-relative v1+ entries safely."""
        candidate = Path(stored_path)
        if candidate.is_absolute():
            return candidate
        resolved = (self.root / candidate).resolve()
        try:
            resolved.relative_to(self.root.resolve())
        except ValueError as exc:
            raise RawRecordingStoreError(
                f"Manifest local path escapes store root: {stored_path}"
            ) from exc
        return resolved

    @staticmethod
    def _atomic_write_bytes(path: Path, payload: bytes) -> None:
        atomic_write_bytes(path, payload)

    @staticmethod
    def _path_parts(device_path: str) -> tuple[int, str, str, str]:
        match = RECORDING_PATH_RE.fullmatch(device_path)
        if match is None:
            raise RawRecordingStoreError(f"Not a Polar offline recording path: {device_path}")
        return (
            int(match.group("user")),
            match.group("date"),
            match.group("time"),
            Path(match.group("filename")).stem.upper(),
        )
