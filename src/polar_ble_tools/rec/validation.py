"""Streaming validation for project-owned decoded REC JSONL."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from polar_ble_tools.rec.models import DecoderProtocolError

PROTOCOL_VERSION = 1
_MAX_JSONL_LINE_BYTES = 1_048_576
_COMMIT_RE = re.compile(r"[0-9a-f]{40}")
_DIGEST_RE = re.compile(r"[0-9a-f]{64}")
_RECORD_TYPE_RE = re.compile(r"[a-z][a-z0-9_]*")


def _reject_non_finite_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant: {value}")


def _json_row(line: bytes, line_number: int) -> dict[str, Any]:
    try:
        value = json.loads(line, parse_constant=_reject_non_finite_constant)
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise DecoderProtocolError(
            f"Decoder output has invalid JSON on line {line_number}."
        ) from exc
    if not isinstance(value, dict):
        raise DecoderProtocolError(f"Decoder output row {line_number} is not a JSON object.")
    return value


def iter_json_rows(path: Path) -> Iterator[tuple[int, dict[str, Any]]]:
    if not path.is_file() or path.is_symlink():
        raise DecoderProtocolError("Decoder output is missing or unsafe.")
    try:
        with path.open("rb") as output:
            for line_number, line in enumerate(output, start=1):
                if len(line) > _MAX_JSONL_LINE_BYTES:
                    raise DecoderProtocolError("Decoder output contains an oversized JSONL row.")
                if line.strip():
                    yield line_number, _json_row(line, line_number)
    except OSError as exc:
        raise DecoderProtocolError("Decoder output could not be read.") from exc


def _validate_header(header: dict[str, Any], source_digest: str) -> None:
    if (
        header.get("type") != "header"
        or header.get("protocol_version") != PROTOCOL_VERSION
        or header.get("source_sha256") != source_digest
        or not isinstance(header.get("decoder_version"), str)
        or not header["decoder_version"]
        or not isinstance(header.get("sdk_commit"), str)
        or not _COMMIT_RE.fullmatch(header["sdk_commit"])
        or not isinstance(header.get("source_sha256"), str)
        or not _DIGEST_RE.fullmatch(header["source_sha256"])
    ):
        raise DecoderProtocolError("Decoder output has an invalid protocol header.")


def validated_rows(path: Path, source_digest: str | None) -> tuple[dict[str, Any], dict[str, Any]]:
    header: dict[str, Any] | None = None
    summary: dict[str, Any] | None = None
    counts: dict[str, int] = {}
    record_count = 0
    for line_number, record in iter_json_rows(path):
        if header is None:
            expected_digest = source_digest or record.get("source_sha256")
            if not isinstance(expected_digest, str):
                raise DecoderProtocolError("Decoder output has an invalid protocol header.")
            _validate_header(record, expected_digest)
            header = record
            continue
        if summary is not None:
            raise DecoderProtocolError(
                f"Decoder output has a row after its summary (line {line_number})."
            )
        if record.get("type") == "summary":
            summary = record
            continue
        if record.get("type") != "record":
            raise DecoderProtocolError("Decoder output contains an invalid record.")
        record_type, timestamp, payload = (
            record.get("record_type"),
            record.get("timestamp_ns"),
            record.get("payload"),
        )
        if (
            not isinstance(record_type, str)
            or not _RECORD_TYPE_RE.fullmatch(record_type)
            or not isinstance(payload, dict)
        ):
            raise DecoderProtocolError("Decoder record has an invalid envelope.")
        if timestamp is not None and (
            not isinstance(timestamp, int) or isinstance(timestamp, bool)
        ):
            raise DecoderProtocolError("Decoder record timestamp is invalid.")
        counts[record_type] = counts.get(record_type, 0) + 1
        record_count += 1
    if header is None or summary is None:
        raise DecoderProtocolError("Decoder output is missing protocol header or summary.")
    if summary.get("record_count") != record_count or summary.get("record_types") != counts:
        raise DecoderProtocolError("Decoder summary does not match its record stream.")
    if not isinstance(summary.get("warnings"), list) or not all(
        isinstance(warning, str) for warning in summary["warnings"]
    ):
        raise DecoderProtocolError("Decoder summary warnings are invalid.")
    return header, summary


__all__ = ["PROTOCOL_VERSION", "iter_json_rows", "validated_rows"]
