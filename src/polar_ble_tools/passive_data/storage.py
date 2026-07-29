from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from polar_ble_tools.storage_utils import append_json_line, atomic_write_bytes, sha256_file

SCHEMA_VERSION = 1
DECODE_SCHEMA_VERSION = 2
SUPPORTED_SCHEMA_VERSIONS = frozenset({SCHEMA_VERSION, DECODE_SCHEMA_VERSION})
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
    logical_date_source: str | None = None
    schema_commit: str | None = None
    schema_manifest_format: int | None = None
    descriptor_sha256: str | None = None
    schema_id: str | None = None
    message_type: str | None = None
    decoded_path: str | None = None
    decoded_sha256: str | None = None
    enriched_at: str | None = None

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
            logical_date_source=(
                str(raw["logical_date_source"])
                if raw.get("logical_date_source") is not None
                else None
            ),
            schema_commit=(
                str(raw["schema_commit"]) if raw.get("schema_commit") is not None else None
            ),
            schema_manifest_format=(
                int(raw["schema_manifest_format"])
                if raw.get("schema_manifest_format") is not None
                else None
            ),
            descriptor_sha256=(
                str(raw["descriptor_sha256"]) if raw.get("descriptor_sha256") is not None else None
            ),
            schema_id=str(raw["schema_id"]) if raw.get("schema_id") is not None else None,
            message_type=(
                str(raw["message_type"]) if raw.get("message_type") is not None else None
            ),
            decoded_path=(
                str(raw["decoded_path"]) if raw.get("decoded_path") is not None else None
            ),
            decoded_sha256=(
                str(raw["decoded_sha256"]) if raw.get("decoded_sha256") is not None else None
            ),
            enriched_at=(str(raw["enriched_at"]) if raw.get("enriched_at") is not None else None),
        )

    def to_jsonable(self) -> dict[str, object]:
        value: dict[str, object] = {
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
        if self.schema_version >= DECODE_SCHEMA_VERSION:
            value.update(
                {
                    "decoded_path": self.decoded_path,
                    "decoded_sha256": self.decoded_sha256,
                    "descriptor_sha256": self.descriptor_sha256,
                    "enriched_at": self.enriched_at,
                    "logical_date_source": self.logical_date_source,
                    "message_type": self.message_type,
                    "schema_commit": self.schema_commit,
                    "schema_id": self.schema_id,
                    "schema_manifest_format": self.schema_manifest_format,
                }
            )
        return value


class PassiveFileStore:
    def __init__(self, root: str | Path = DEFAULT_PASSIVE_ROOT) -> None:
        self.root = Path(root)

    def sanitize_device_id(self, device_id: str) -> str:
        sanitized = DEVICE_ID_RE.sub("", device_id).upper()
        if not sanitized:
            raise PassiveFileStoreError("Device id does not contain alphanumeric characters.")
        return sanitized

    def manifest_path(self, device_id: str) -> Path:
        path = self.root / self.sanitize_device_id(device_id) / MANIFEST_FILENAME
        _reject_symlinks(self.root, path)
        return path

    def deletion_audit_path(self, device_id: str) -> Path:
        path = self.root / self.sanitize_device_id(device_id) / DELETION_AUDIT_FILENAME
        _reject_symlinks(self.root, path)
        return path

    def local_file_path(self, device_id: str, device_path: str) -> Path:
        parts = _safe_device_path_parts(device_path)
        path = self.root / self.sanitize_device_id(device_id) / "files" / Path(*parts)
        _reject_symlinks(self.root, path)
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
        if path.is_symlink() or not path.is_file():
            raise PassiveFileStoreError(f"Passive manifest is not a regular file: {path}")
        entries: list[PassiveFileManifestEntry] = []
        rows = path.read_bytes().split(b"\n")
        if rows and rows[-1]:
            rows.pop()
        for line_number, row in enumerate(rows, 1):
            if not row.strip():
                continue
            try:
                entry = PassiveFileManifestEntry.from_jsonable(json.loads(row))
                if entry.schema_version not in SUPPORTED_SCHEMA_VERSIONS:
                    raise ValueError("unsupported schema version")
                entries.append(entry)
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
                entry.schema_version not in SUPPORTED_SCHEMA_VERSIONS
                or entry.device_id != expected_device_id
                or entry.device_path != device_path
                or (domain is not None and entry.domain != domain)
                or entry.status != "fetched"
                or entry.device_size != device_size
                or entry.fetched_size != device_size
            ):
                continue
            path = self.resolve_local_path(entry.local_path)
            if path.is_symlink() or not path.is_file() or path.stat().st_size != device_size:
                continue
            if sha256_file(path) == entry.sha256:
                return entry
        return None

    def append_decode_enrichment(
        self,
        device_id: str,
        source: PassiveFileManifestEntry,
        *,
        logical_date: str | None,
        logical_date_source: str | None,
        schema_commit: str,
        schema_manifest_format: int,
        descriptor_sha256: str,
        schema_id: str,
        message_type: str,
        decoded_path: str | Path,
        decoded_sha256: str,
        enriched_at: datetime | None = None,
    ) -> PassiveFileManifestEntry:
        """Append decode evidence after re-verifying immutable raw and JSON files."""
        expected_device_id = self.sanitize_device_id(device_id)
        if (
            source.device_id != expected_device_id
            or source.schema_version not in SUPPORTED_SCHEMA_VERSIONS
            or source.status != "fetched"
            or source.device_size != source.fetched_size
        ):
            raise PassiveFileStoreError("Decode enrichment source is not a valid fetched row.")
        if (
            not re.fullmatch(r"[0-9a-f]{40}", schema_commit)
            or schema_manifest_format not in {2, 3}
            or not re.fullmatch(r"[0-9a-f]{64}", descriptor_sha256)
            or not re.fullmatch(r"[0-9a-f]{64}", decoded_sha256)
            or (logical_date is None) != (logical_date_source is None)
        ):
            raise PassiveFileStoreError("Decode enrichment provenance is incomplete or invalid.")
        raw_path = self.resolve_local_path(source.local_path)
        if (
            raw_path.is_symlink()
            or not raw_path.is_file()
            or raw_path.stat().st_size != source.fetched_size
            or sha256_file(raw_path) != source.sha256
        ):
            raise PassiveFileStoreError("Raw passive evidence changed before decode enrichment.")
        if logical_date is not None:
            try:
                date.fromisoformat(logical_date)
            except ValueError as exc:
                raise PassiveFileStoreError(
                    f"Decoded logical date is invalid: {logical_date}"
                ) from exc
        decoded = Path(decoded_path)
        if decoded.is_absolute():
            try:
                decoded = decoded.resolve().relative_to(self.root.resolve())
            except ValueError as exc:
                raise PassiveFileStoreError("Decoded output escapes passive store root.") from exc
        decoded_file = self.resolve_local_path(decoded.as_posix())
        if (
            decoded_file.is_symlink()
            or not decoded_file.is_file()
            or sha256_file(decoded_file) != decoded_sha256
        ):
            raise PassiveFileStoreError("Decoded output evidence is unavailable or invalid.")
        timestamp = (enriched_at or datetime.now(UTC)).astimezone(UTC)
        entry = PassiveFileManifestEntry(
            schema_version=DECODE_SCHEMA_VERSION,
            device_id=expected_device_id,
            device_path=source.device_path,
            local_path=source.local_path,
            domain=source.domain,
            logical_date=logical_date,
            device_size=source.device_size,
            fetched_size=source.fetched_size,
            sha256=source.sha256,
            fetched_at=source.fetched_at,
            status=source.status,
            logical_date_source=logical_date_source,
            schema_commit=schema_commit,
            schema_manifest_format=schema_manifest_format,
            descriptor_sha256=descriptor_sha256,
            schema_id=schema_id,
            message_type=message_type,
            decoded_path=decoded.as_posix(),
            decoded_sha256=decoded_sha256,
            enriched_at=timestamp.isoformat().replace("+00:00", "Z"),
        )
        append_json_line(self.manifest_path(device_id), entry.to_jsonable())
        return entry

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
        unresolved = self.root / candidate
        _reject_symlinks(self.root, unresolved)
        resolved = unresolved.resolve()
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


def _reject_symlinks(root: Path, path: Path) -> None:
    if root.is_symlink():
        raise PassiveFileStoreError(f"Passive store root is a symlink: {root}")
    current = root
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise PassiveFileStoreError(f"Passive path escapes store root: {path}") from exc
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise PassiveFileStoreError(f"Passive path contains a symlink: {current}")
