from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from polar_ble_tools.storage_utils import append_json_line, atomic_write_bytes, sha256_file

SCHEMA_VERSION = 1
DEFAULT_PASSIVE_ROOT = Path(".local/polar-ble-passive")
MANIFEST_FILENAME = "manifest.jsonl"
DELETION_AUDIT_FILENAME = "deletion-audit.jsonl"
DEVICE_ID_RE = re.compile(r"[^A-Za-z0-9]+")


class PassiveFileStoreError(RuntimeError):
    """Raised when passive-file storage cannot verify its local state."""


@dataclass(frozen=True)
class PassiveFileManifestEntry:
    schema_version: int
    device_id: str
    device_path: str
    local_path: str
    domain: str
    logical_date: str | None
    device_size: int
    fetched_size: int
    sha256: str
    fetched_at: str
    status: str

    @classmethod
    def from_jsonable(cls, raw: dict[str, Any]) -> PassiveFileManifestEntry:
        return cls(
            schema_version=int(raw["schema_version"]),
            device_id=str(raw["device_id"]),
            device_path=str(raw["device_path"]),
            local_path=str(raw["local_path"]),
            domain=str(raw["domain"]),
            logical_date=str(raw["logical_date"]) if raw["logical_date"] is not None else None,
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
            "domain": self.domain,
            "fetched_at": self.fetched_at,
            "fetched_size": self.fetched_size,
            "local_path": self.local_path,
            "logical_date": self.logical_date,
            "schema_version": self.schema_version,
            "sha256": self.sha256,
            "status": self.status,
        }


class PassiveFileStore:
    def __init__(self, root: str | Path = DEFAULT_PASSIVE_ROOT) -> None:
        self.root = Path(root)

    def sanitize_device_id(self, device_id: str) -> str:
        sanitized = DEVICE_ID_RE.sub("", device_id).upper()
        if not sanitized:
            raise PassiveFileStoreError("Device id does not contain alphanumeric characters.")
        return sanitized

    def manifest_path(self, device_id: str) -> Path:
        return self.root / self.sanitize_device_id(device_id) / MANIFEST_FILENAME

    def deletion_audit_path(self, device_id: str) -> Path:
        return self.root / self.sanitize_device_id(device_id) / DELETION_AUDIT_FILENAME

    def local_file_path(self, device_id: str, device_path: str) -> Path:
        parts = _safe_device_path_parts(device_path)
        path = self.root / self.sanitize_device_id(device_id) / "files" / Path(*parts)
        try:
            path.resolve().relative_to(self.root.resolve())
        except ValueError as exc:  # pragma: no cover - parts validation invariant
            raise PassiveFileStoreError(
                f"Passive file path escapes store root: {device_path}"
            ) from exc
        return path

    def read_manifest(self, device_id: str) -> list[PassiveFileManifestEntry]:
        path = self.manifest_path(device_id)
        if not path.exists():
            return []
        entries: list[PassiveFileManifestEntry] = []
        rows = path.read_bytes().split(b"\n")
        if rows and rows[-1]:
            rows.pop()
        for line_number, row in enumerate(rows, 1):
            if not row.strip():
                continue
            try:
                entries.append(PassiveFileManifestEntry.from_jsonable(json.loads(row)))
            except (
                UnicodeDecodeError,
                KeyError,
                TypeError,
                ValueError,
                json.JSONDecodeError,
            ) as exc:
                raise PassiveFileStoreError(
                    f"Invalid manifest entry at {path}:{line_number}."
                ) from exc
        return entries

    def persist_file(
        self,
        device_id: str,
        *,
        domain: str,
        device_path: str,
        device_size: int,
        payload: bytes,
        logical_date: str | None,
        fetched_at: datetime | None = None,
    ) -> PassiveFileManifestEntry:
        if len(payload) != device_size:
            raise PassiveFileStoreError(
                f"Fetched byte count for {device_path} does not match device directory size."
            )
        final_path = self.local_file_path(device_id, device_path)
        atomic_write_bytes(final_path, payload)
        entry = PassiveFileManifestEntry(
            schema_version=SCHEMA_VERSION,
            device_id=self.sanitize_device_id(device_id),
            device_path=device_path,
            local_path=final_path.relative_to(self.root).as_posix(),
            domain=domain,
            logical_date=logical_date,
            device_size=device_size,
            fetched_size=len(payload),
            sha256=hashlib.sha256(payload).hexdigest(),
            fetched_at=(fetched_at or datetime.now(UTC))
            .astimezone(UTC)
            .isoformat()
            .replace("+00:00", "Z"),
            status="fetched",
        )
        append_json_line(self.manifest_path(device_id), entry.to_jsonable())
        return entry

    def verify_existing_file(
        self,
        device_id: str,
        *,
        device_path: str,
        device_size: int,
        domain: str | None = None,
    ) -> PassiveFileManifestEntry | None:
        expected_device_id = self.sanitize_device_id(device_id)
        for entry in reversed(self.read_manifest(device_id)):
            if (
                entry.schema_version != SCHEMA_VERSION
                or entry.device_id != expected_device_id
                or entry.device_path != device_path
                or (domain is not None and entry.domain != domain)
                or entry.status != "fetched"
                or entry.device_size != device_size
                or entry.fetched_size != device_size
            ):
                continue
            path = self.resolve_local_path(entry.local_path)
            if not path.is_file() or path.stat().st_size != device_size:
                continue
            if sha256_file(path) == entry.sha256:
                return entry
        return None

    def append_deletion_audit(
        self,
        device_id: str,
        *,
        operation_id: str,
        domain: str,
        logical_date: str | None,
        device_path: str,
        local_path: str | None,
        local_sha256: str | None,
        status: str,
        deleted_paths: tuple[str, ...] = (),
        error: str | None = None,
        dry_run: bool = False,
        observed_at: datetime | None = None,
    ) -> None:
        """Append one immutable, payload-free passive deletion audit row."""
        timestamp = (observed_at or datetime.now(UTC)).astimezone(UTC)
        append_json_line(
            self.deletion_audit_path(device_id),
            {
                "observed_at": timestamp.isoformat().replace("+00:00", "Z"),
                "operation_id": operation_id,
                "schema_version": SCHEMA_VERSION,
                "device_id": self.sanitize_device_id(device_id),
                "domain": domain,
                "logical_date": logical_date,
                "device_path": device_path,
                "local_path": local_path,
                "local_sha256": local_sha256,
                "status": status,
                "deleted_paths": list(deleted_paths),
                "error": error,
                "dry_run": dry_run,
            },
        )

    def resolve_local_path(self, stored_path: str) -> Path:
        candidate = Path(stored_path)
        if candidate.is_absolute():
            raise PassiveFileStoreError("Passive manifest paths must be store-relative.")
        resolved = (self.root / candidate).resolve()
        try:
            resolved.relative_to(self.root.resolve())
        except ValueError as exc:
            raise PassiveFileStoreError(
                f"Manifest local path escapes store root: {stored_path}"
            ) from exc
        return resolved


def _safe_device_path_parts(device_path: str) -> tuple[str, ...]:
    path = PurePosixPath(device_path)
    parts = tuple(part for part in path.parts if part != "/")
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise PassiveFileStoreError(f"Invalid passive device path: {device_path}")
    return parts
