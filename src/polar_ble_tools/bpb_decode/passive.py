from __future__ import annotations

import re
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

from polar_ble_tools.bpb_decode.core import decode_bpb_file, publish_decode_result
from polar_ble_tools.bpb_decode.models import (
    FAILED_STATUS,
    SUPPORTED_STATUS,
    UNSUPPORTED_STATUS,
    BpbDecodeResult,
    BpbManifestDecodeResult,
    BpbManifestError,
)
from polar_ble_tools.passive_data.storage import (
    MANIFEST_FILENAME,
    PassiveFileManifestEntry,
    PassiveFileStore,
    PassiveFileStoreError,
)

_DATED_PATH = re.compile(r"^/U/\d+/(?P<date>\d{8})/", re.IGNORECASE)
_PAYLOAD_DATE_FIELDS: dict[str, tuple[str, ...]] = {
    "activity_samples": ("start_time", "date"),
    "automatic_sample_sessions": ("day",),
    "daily_summary": ("date",),
    "sleep_analysis": ("sleep_date",),
    "sleep_skin_temperature_result": ("sleep_date",),
}


def decode_passive_manifest(
    manifest_path: str | Path,
    *,
    output_dir: str | Path | None = None,
) -> BpbManifestDecodeResult:
    """Decode the latest fetched evidence row for each passive device path."""
    manifest = Path(manifest_path)
    if manifest.name != MANIFEST_FILENAME or manifest.is_symlink() or not manifest.is_file():
        raise BpbManifestError("Passive decoding requires a regular passive manifest.jsonl.")
    store_root = manifest.parent.parent
    store = PassiveFileStore(store_root)
    device_id = manifest.parent.name
    if store.manifest_path(device_id).resolve() != manifest.resolve():
        raise BpbManifestError("Passive manifest path does not match its device store.")
    if output_dir is None:
        decoded_root = manifest.parent / "decoded"
    else:
        decoded_root = Path(output_dir)
        if not decoded_root.is_absolute():
            decoded_root = store.root / decoded_root
    try:
        decoded_root.resolve(strict=False).relative_to(store.root.resolve())
    except ValueError as exc:
        raise BpbManifestError(
            "Decoded passive output must remain inside the passive store."
        ) from exc
    try:
        entries = store.read_manifest(device_id)
    except PassiveFileStoreError as exc:
        raise BpbManifestError(str(exc)) from exc
    latest: dict[str, tuple[int, PassiveFileManifestEntry]] = {}
    for index, entry in enumerate(entries):
        if entry.status == "fetched":
            latest[entry.device_path] = (index, entry)
    selected = [entry for _, entry in sorted(latest.values(), key=lambda item: item[0])]
    results: list[BpbDecodeResult] = []
    for entry in selected:
        try:
            local = store.resolve_local_path(entry.local_path)
        except PassiveFileStoreError as exc:
            result = _source_failure(entry, store.root / ".invalid", str(exc))
        else:
            result = decode_bpb_file(local, device_path=entry.device_path)
            if (
                result.file_size != entry.fetched_size
                or result.sha256 != entry.sha256
                or entry.device_size != entry.fetched_size
            ):
                result = _source_failure(
                    entry,
                    local,
                    "Passive manifest payload integrity mismatch.",
                    result.file_size,
                    result.sha256,
                )
            elif result.status == SUPPORTED_STATUS:
                result = _with_logical_date(result, entry)
        result = publish_decode_result(decoded_root, result)
        if result.status == SUPPORTED_STATUS:
            try:
                _append_enrichment(store, device_id, entry, result)
            except BpbManifestError as exc:
                result = replace(
                    result,
                    status=FAILED_STATUS,
                    error_code="manifest_invalid",
                    error=str(exc),
                )
                result = publish_decode_result(decoded_root, result)
        results.append(result)
    return BpbManifestDecodeResult(
        str(manifest),
        str(decoded_root),
        len(results),
        sum(result.status == SUPPORTED_STATUS for result in results),
        sum(result.status == UNSUPPORTED_STATUS for result in results),
        sum(result.status == FAILED_STATUS for result in results),
        tuple(results),
    )


def _with_logical_date(result: BpbDecodeResult, entry: PassiveFileManifestEntry) -> BpbDecodeResult:
    payload_date, payload_source = _payload_date(result)
    path_date = _path_date(entry.device_path)
    evidence_dates = {
        value for value in (entry.logical_date, path_date, payload_date) if value is not None
    }
    if len(evidence_dates) > 1:
        return replace(
            result,
            status=FAILED_STATUS,
            data=None,
            error_code="logical_date_mismatch",
            error=(
                "Decoded payload, passive manifest, and device path disagree on "
                f"logical date: {', '.join(sorted(evidence_dates))}."
            ),
            logical_date=None,
            logical_date_source=None,
        )
    if payload_date is not None:
        return replace(
            result,
            logical_date=payload_date,
            logical_date_source=payload_source,
        )
    expected = entry.logical_date or path_date
    if expected is not None:
        return replace(
            result,
            logical_date=expected,
            logical_date_source=entry.logical_date_source or "device_path",
        )
    return result


def _payload_date(result: BpbDecodeResult) -> tuple[str | None, str | None]:
    fields = _PAYLOAD_DATE_FIELDS.get(result.schema_id or "")
    value: Any = result.data
    if fields is None or not isinstance(value, dict):
        return None, None
    for field in fields:
        value = value.get(field)
        if not isinstance(value, dict):
            return None, None
    try:
        logical = date(int(value["year"]), int(value["month"]), int(value["day"]))
    except (KeyError, TypeError, ValueError):
        return None, None
    return logical.isoformat(), "payload." + ".".join(fields)


def _path_date(device_path: str) -> str | None:
    match = _DATED_PATH.match(device_path)
    if match is None:
        return None
    try:
        return date.fromisoformat(
            f"{match['date'][:4]}-{match['date'][4:6]}-{match['date'][6:]}"
        ).isoformat()
    except ValueError:
        return None


def _append_enrichment(
    store: PassiveFileStore,
    device_id: str,
    source: PassiveFileManifestEntry,
    result: BpbDecodeResult,
) -> None:
    required = (
        result.schema_commit,
        result.descriptor_sha256,
        result.schema_id,
        result.message_type,
        result.decoded_path,
        result.decoded_sha256,
    )
    if result.schema_manifest_format is None or any(value is None for value in required):
        raise BpbManifestError("Decoded BPB result is missing schema or output provenance.")
    try:
        decoded_relative = (
            Path(str(result.decoded_path)).resolve().relative_to(store.root.resolve())
        )
    except ValueError as exc:
        raise BpbManifestError("Decoded BPB output escapes the passive store.") from exc
    if (
        source.schema_version == 2
        and source.logical_date == result.logical_date
        and source.logical_date_source == result.logical_date_source
        and source.schema_commit == result.schema_commit
        and source.descriptor_sha256 == result.descriptor_sha256
        and source.decoded_path == decoded_relative.as_posix()
        and source.decoded_sha256 == result.decoded_sha256
    ):
        return
    try:
        store.append_decode_enrichment(
            device_id,
            source,
            logical_date=result.logical_date,
            logical_date_source=result.logical_date_source,
            schema_commit=str(result.schema_commit),
            schema_manifest_format=result.schema_manifest_format,
            descriptor_sha256=str(result.descriptor_sha256),
            schema_id=str(result.schema_id),
            message_type=str(result.message_type),
            decoded_path=decoded_relative,
            decoded_sha256=str(result.decoded_sha256),
        )
    except (PassiveFileStoreError, ValueError) as exc:
        raise BpbManifestError(f"Cannot persist passive decode evidence: {exc}") from exc


def _source_failure(
    entry: PassiveFileManifestEntry,
    local: Path,
    error: str,
    size: int | None = None,
    digest: str | None = None,
) -> BpbDecodeResult:
    return BpbDecodeResult(
        FAILED_STATUS,
        str(local),
        entry.device_path,
        size,
        digest,
        None,
        None,
        None,
        error=error,
        error_code="source_evidence_mismatch",
    )
