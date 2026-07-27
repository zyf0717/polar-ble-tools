"""Project-owned REC decoder models and stable error categories."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


class RecDecodeError(RuntimeError):
    """Base error for local REC decoding."""


class DecoderUnavailableError(RecDecodeError):
    """No active verified local decoder is available."""


class DecoderManifestError(RecDecodeError):
    """The active decoder manifest is malformed or unsafe."""


class DecoderVerificationError(RecDecodeError):
    """The active decoder no longer matches its verified manifest."""


class DecoderProtocolError(RecDecodeError):
    """The sidecar's protocol output is invalid."""


class DecoderTimeoutError(RecDecodeError):
    """The local decoder exceeded its deadline."""


class RecordingDecodeError(RecDecodeError):
    """The local decoder could not decode the recording."""


class UnsupportedRecordingError(RecDecodeError):
    """The official SDK parser does not support the selected recording."""


@dataclass(frozen=True)
class DecoderStatus:
    available: bool
    verified: bool
    sdk_commit: str | None
    protocol_version: int | None
    verification_level: str | None
    reason: str | None


@dataclass(frozen=True)
class DecodeReport:
    source_path: Path
    destination_path: Path
    source_sha256: str
    destination_sha256: str
    sdk_commit: str
    decoder_version: str
    record_count: int
    record_types: Mapping[str, int]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class RecRecord:
    record_type: str
    timestamp_ns: int | None
    payload: Mapping[str, object]


__all__ = [
    "DecodeReport",
    "DecoderManifestError",
    "DecoderProtocolError",
    "DecoderStatus",
    "DecoderTimeoutError",
    "DecoderUnavailableError",
    "DecoderVerificationError",
    "RecDecodeError",
    "RecRecord",
    "RecordingDecodeError",
    "UnsupportedRecordingError",
]
