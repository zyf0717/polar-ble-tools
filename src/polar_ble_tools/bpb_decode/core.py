from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import replace
from pathlib import Path
from typing import Any

from google.protobuf.json_format import MessageToDict
from google.protobuf.message import DecodeError

from polar_ble_tools.bpb_decode.models import (
    FAILED_STATUS,
    SUPPORTED_STATUS,
    UNSUPPORTED_STATUS,
    BpbDecodeResult,
    BpbManifestDecodeResult,
    BpbManifestError,
)
from polar_ble_tools.bpb_decode.paths import (
    decoded_output_path,
    infer_device_path,
    normalize_device_path,
)
from polar_ble_tools.bpb_decode.schemas import BpbSchema, schema_for_bpb
from polar_ble_tools.schemas.errors import SchemaUnavailableError
from polar_ble_tools.schemas.runtime import schema_activation_manager
from polar_ble_tools.sdk_tools.verifier import (
    SchemaVerificationError,
    schema_provenance,
)
from polar_ble_tools.storage_utils import atomic_write_bytes

MAX_BPB_BYTES = 64 * 1024 * 1024
MAX_MANIFEST_BYTES = 16 * 1024 * 1024
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class _BpbInputError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def decode_bpb_file(path: str | Path, *, device_path: str | None = None) -> BpbDecodeResult:
    local = Path(path)
    try:
        normalized = normalize_device_path(device_path) if device_path else None
    except ValueError as exc:
        return _failed(local, None, str(exc), error_code="unsafe_input")
    if local.suffix.upper() != ".BPB":
        return _failed(
            local,
            normalized,
            "Input path must point to a .BPB file.",
            error_code="unsafe_input",
        )
    try:
        payload = _read_regular(local, maximum=MAX_BPB_BYTES)
    except _BpbInputError as exc:
        return _failed(local, normalized, str(exc), error_code=exc.code)
    return _decode(local, normalized or infer_device_path(local), payload)


def decode_bpb_manifest(
    manifest_path: str | Path,
    *,
    output_dir: str | Path | None = None,
    source_root: str | Path | None = None,
) -> BpbManifestDecodeResult:
    manifest = Path(manifest_path)
    root = Path(output_dir) if output_dir is not None else manifest.parent / "decoded"
    inputs = Path(source_root) if source_root is not None else manifest.parent
    results: list[BpbDecodeResult] = []
    for number, row in _rows(manifest):
        if row.get("status") != "fetched":
            continue
        local = _manifest_local_path(row, inputs)
        device = _device_path(row)
        try:
            expected_size, expected_hash = int(row["fetched_size"]), str(row["sha256"]).lower()
            if expected_size < 0 or not _SHA256_RE.fullmatch(expected_hash):
                raise ValueError("invalid size or SHA-256")
            payload = _read_regular(local, maximum=MAX_BPB_BYTES, root=inputs)
        except (KeyError, TypeError, ValueError, _BpbInputError) as exc:
            code = exc.code if isinstance(exc, _BpbInputError) else "manifest_invalid"
            result = _failed(
                local,
                device,
                f"Manifest row {number} is invalid: {exc}",
                error_code=code,
            )
        else:
            actual = _sha256(payload)
            if len(payload) != expected_size or actual != expected_hash:
                result = _failed(
                    local,
                    device,
                    f"Manifest row {number} payload integrity mismatch.",
                    len(payload),
                    actual,
                    error_code="source_evidence_mismatch",
                )
            else:
                result = _decode(local, device, payload)
        results.append(publish_decode_result(root, result))
    return BpbManifestDecodeResult(
        str(manifest),
        str(root),
        len(results),
        sum(r.status == SUPPORTED_STATUS for r in results),
        sum(r.status == UNSUPPORTED_STATUS for r in results),
        sum(r.status == FAILED_STATUS for r in results),
        tuple(results),
    )


def publish_decode_result(output_root: str | Path, result: BpbDecodeResult) -> BpbDecodeResult:
    """Atomically publish one owner-private result beneath an output root."""
    root = Path(output_root)
    try:
        path = decoded_output_path(root, result)
    except ValueError:
        path = (
            root
            / f"failed-{hashlib.sha256((result.local_path + str(result.device_path)).encode()).hexdigest()[:16]}.json"
        )
    try:
        _validate_output_path(root, path)
        published = replace(result, decoded_path=None, decoded_sha256=None)
        payload = (json.dumps(published.to_jsonable(), indent=2, sort_keys=True) + "\n").encode(
            "utf-8"
        )
        atomic_write_bytes(path, payload)
    except ValueError as exc:
        return replace(
            result,
            status=FAILED_STATUS,
            error_code="unsafe_output",
            error=f"Cannot publish decoded BPB result: {exc}",
            decoded_path=None,
            decoded_sha256=None,
        )
    except OSError as exc:
        return replace(
            result,
            status=FAILED_STATUS,
            error_code="output_write_failed",
            error=f"Cannot publish decoded BPB result: {exc}",
            decoded_path=None,
            decoded_sha256=None,
        )
    return replace(
        result,
        decoded_path=str(path),
        decoded_sha256=_sha256(payload),
    )


def _decode(local: Path, device: str | None, payload: bytes) -> BpbDecodeResult:
    schema = schema_for_bpb(device_path=device, local_path=local)
    digest = _sha256(payload)
    if schema is None:
        return BpbDecodeResult(
            UNSUPPORTED_STATUS,
            str(local),
            device,
            len(payload),
            digest,
            None,
            None,
            None,
            reason="No registered protobuf schema matches this BPB path.",
        )
    try:
        message = schema.message_class()
        commit = schema_activation_manager().active_commit
        if commit is None:  # pragma: no cover - require_modules establishes this invariant
            raise SchemaVerificationError("No schema revision is active in this process.")
        provenance = schema_provenance(commit=commit)
    except (SchemaUnavailableError, SchemaVerificationError) as exc:
        return _failed(
            local,
            device,
            str(exc),
            len(payload),
            digest,
            schema,
            error_code="schema_unavailable",
        )
    try:
        message.ParseFromString(payload)
    except DecodeError as exc:
        return _failed(
            local,
            device,
            f"Protobuf decode failed: {exc}",
            len(payload),
            digest,
            schema,
            error_code="protobuf_parse_failed",
            provenance=provenance,
        )
    if not message.IsInitialized():
        return _failed(
            local,
            device,
            "Protobuf message missing required fields: "
            + ", ".join(message.FindInitializationErrors()),
            len(payload),
            digest,
            schema,
            error_code="protobuf_uninitialized",
            provenance=provenance,
        )
    return BpbDecodeResult(
        SUPPORTED_STATUS,
        str(local),
        device,
        len(payload),
        digest,
        schema.schema_id,
        message.DESCRIPTOR.full_name,
        MessageToDict(message, preserving_proto_field_name=True, use_integers_for_enums=False),
        schema_commit=provenance.resolved_commit,
        schema_manifest_format=provenance.manifest_format,
        descriptor_sha256=provenance.descriptor_sha256,
    )


def _failed(
    local: Path,
    device: str | None,
    error: str,
    size: int | None = None,
    digest: str | None = None,
    schema: BpbSchema | None = None,
    *,
    error_code: str,
    provenance=None,
) -> BpbDecodeResult:
    return BpbDecodeResult(
        FAILED_STATUS,
        str(local),
        device,
        size,
        digest,
        schema.schema_id if schema else None,
        None,
        None,
        error=error,
        error_code=error_code,
        schema_commit=provenance.resolved_commit if provenance else None,
        schema_manifest_format=provenance.manifest_format if provenance else None,
        descriptor_sha256=provenance.descriptor_sha256 if provenance else None,
    )


def _rows(path: Path) -> list[tuple[int, dict[str, Any]]]:
    try:
        content = _read_regular(path, maximum=MAX_MANIFEST_BYTES)
        lines = content.decode("utf-8").splitlines()
    except (UnicodeDecodeError, _BpbInputError) as exc:
        raise BpbManifestError(f"Cannot read manifest safely: {exc}") from exc
    rows = []
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise BpbManifestError(
                f"Invalid JSON in manifest at line {number}: {exc.msg}."
            ) from exc
        if not isinstance(row, dict):
            raise BpbManifestError(f"Invalid manifest row at line {number}: expected object.")
        rows.append((number, row))
    return rows


def _manifest_local_path(row: dict[str, Any], root: Path) -> Path:
    raw = str(row.get("local_path", ""))
    if not raw:
        return root / ".missing"
    local = Path(raw)
    return local if local.is_absolute() else root / local


def _device_path(row: dict[str, Any]) -> str | None:
    try:
        return normalize_device_path(str(row["device_path"]))
    except (KeyError, ValueError):
        return None


def _read_regular(path: Path, *, maximum: int, root: Path | None = None) -> bytes:
    if root is not None:
        try:
            path.resolve(strict=False).relative_to(root.resolve())
        except ValueError as exc:
            raise _BpbInputError("unsafe_input", f"Input path escapes its root: {path}") from exc
        _reject_symlink_ancestors(path, root)
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise _BpbInputError("unsafe_input", f"Cannot open regular input file: {exc}") from exc
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise _BpbInputError("unsafe_input", f"Input is not a regular file: {path}")
        if metadata.st_size > maximum:
            raise _BpbInputError(
                "input_too_large",
                f"Input exceeds the {maximum}-byte safety limit: {path}",
            )
        blocks: list[bytes] = []
        total = 0
        while True:
            block = os.read(descriptor, min(1024 * 1024, maximum + 1 - total))
            if not block:
                break
            blocks.append(block)
            total += len(block)
            if total > maximum:
                raise _BpbInputError(
                    "input_too_large",
                    f"Input exceeds the {maximum}-byte safety limit: {path}",
                )
        return b"".join(blocks)
    finally:
        os.close(descriptor)


def _reject_symlink_ancestors(path: Path, root: Path) -> None:
    root = root.resolve()
    candidate = path if path.is_absolute() else path.absolute()
    try:
        relative = candidate.relative_to(root)
    except ValueError:
        return
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise _BpbInputError("unsafe_input", f"Input path contains a symlink: {current}")


def _validate_output_path(root: Path, path: Path) -> None:
    if root.is_symlink():
        raise ValueError(f"Decoded output root is a symlink: {root}")
    resolved_root = root.resolve()
    try:
        path.resolve(strict=False).relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"Decoded output escapes its root: {path}") from exc
    current = resolved_root
    relative = path.absolute().relative_to(resolved_root)
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ValueError(f"Decoded output path contains a symlink: {current}")
    if path.exists() and not path.is_file():
        raise ValueError(f"Decoded output is not a regular file: {path}")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
