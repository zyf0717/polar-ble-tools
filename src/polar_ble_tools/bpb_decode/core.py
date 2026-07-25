from __future__ import annotations

import hashlib
import json
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


def decode_bpb_file(path: str | Path, *, device_path: str | None = None) -> BpbDecodeResult:
    local = Path(path)
    normalized = normalize_device_path(device_path) if device_path else None
    if local.suffix.upper() != ".BPB":
        return _failed(local, normalized, "Input path must point to a .BPB file.")
    try:
        payload = local.read_bytes()
    except OSError as exc:
        return _failed(local, normalized, f"Cannot read local BPB file: {exc}")
    return _decode(local, normalized or infer_device_path(local), payload)


def decode_bpb_manifest(
    manifest_path: str | Path, *, output_dir: str | Path | None = None
) -> BpbManifestDecodeResult:
    manifest = Path(manifest_path)
    root = Path(output_dir) if output_dir is not None else manifest.parent / "decoded"
    results: list[BpbDecodeResult] = []
    for number, row in _rows(manifest):
        if row.get("status") != "fetched":
            continue
        local = Path(str(row.get("local_path", "")))
        if not local.is_absolute() and not local.exists():
            local = manifest.parent / local
        device = _device_path(row)
        try:
            payload = local.read_bytes()
            expected_size, expected_hash = int(row["fetched_size"]), str(row["sha256"]).lower()
        except (OSError, KeyError, TypeError, ValueError) as exc:
            result = _failed(local, device, f"Manifest row {number} is invalid: {exc}")
        else:
            actual = _sha256(payload)
            if len(payload) != expected_size or actual != expected_hash:
                result = _failed(
                    local,
                    device,
                    f"Manifest row {number} payload integrity mismatch.",
                    len(payload),
                    actual,
                )
            else:
                result = _decode(local, device, payload)
        _write(root, result)
        results.append(result)
    return BpbManifestDecodeResult(
        str(manifest),
        str(root),
        len(results),
        sum(r.status == SUPPORTED_STATUS for r in results),
        sum(r.status == UNSUPPORTED_STATUS for r in results),
        sum(r.status == FAILED_STATUS for r in results),
        results,
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
    except SchemaUnavailableError as exc:
        return _failed(
            local,
            device,
            str(exc),
            len(payload),
            digest,
            schema,
        )
    try:
        message.ParseFromString(payload)
    except DecodeError as exc:
        return _failed(
            local, device, f"Protobuf decode failed: {exc}", len(payload), digest, schema
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
    )


def _failed(
    local: Path,
    device: str | None,
    error: str,
    size: int | None = None,
    digest: str | None = None,
    schema: BpbSchema | None = None,
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
    )


def _rows(path: Path) -> list[tuple[int, dict[str, Any]]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise BpbManifestError(f"Cannot read manifest: {exc}") from exc
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


def _device_path(row: dict[str, Any]) -> str | None:
    try:
        return normalize_device_path(str(row["device_path"]))
    except (KeyError, ValueError):
        return None


def _write(root: Path, result: BpbDecodeResult) -> None:
    try:
        path = decoded_output_path(root, result)
    except ValueError:
        path = (
            root
            / f"failed-{hashlib.sha256((result.local_path + str(result.device_path)).encode()).hexdigest()[:16]}.json"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.part")
    temporary.write_text(
        json.dumps(result.to_jsonable(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
