"""Deterministic tree and manifest orchestration for local REC decoding."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path, PurePosixPath
from tempfile import NamedTemporaryFile
from types import MappingProxyType

from polar_ble_tools.rec.api import (
    DecodeReport,
    DecoderManifestError,
    DecoderProtocolError,
    RecDecodeError,
    RecordingDecodeError,
    UnsupportedRecordingError,
    decode_recording,
    iter_decoded_records,
)
from polar_ble_tools.sdk_tools.decoder.toolchain import (
    normalized_architecture,
    normalized_platform,
)

_BATCH_SCHEMA_VERSION = 1
_BATCH_SUMMARY_KIND = "polar_ble_tools_rec_batch_summary"
_DIGEST_RE = re.compile(r"[0-9a-f]{64}")
_MANIFEST_FIELDS = frozenset({"schema_version", "source", "source_sha256", "secret_id"})
_MAX_MANIFEST_LINE_BYTES = 1_048_576


class BatchDecodeStatus(StrEnum):
    DECODED = "decoded"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"


@dataclass(frozen=True)
class BatchFileResult:
    status: BatchDecodeStatus
    relative_path: str
    output_path: str
    source_sha256: str
    output_sha256: str | None = None
    record_type: str | None = None
    record_count: int = 0
    record_types: Mapping[str, int] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    error_code: str | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", BatchDecodeStatus(self.status))
        object.__setattr__(
            self,
            "record_types",
            MappingProxyType(dict(sorted(self.record_types.items()))),
        )
        object.__setattr__(self, "warnings", tuple(self.warnings))

    def to_jsonable(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "source": self.relative_path,
            "relative_path": self.relative_path,
            "output": self.output_path,
            "source_sha256": self.source_sha256,
            "output_sha256": self.output_sha256,
            "record_type": self.record_type,
            "record_count": self.record_count,
            "record_types": dict(self.record_types),
            "warnings": list(self.warnings),
            "error_code": self.error_code,
            "error": self.error,
        }


@dataclass(frozen=True)
class BatchDecodeReport:
    mode: str
    source_root: Path
    output_root: Path
    summary_path: Path
    files: tuple[BatchFileResult, ...]
    sdk_commit: str | None
    decoder_version: str | None
    protocol_version: int
    platform: str
    architecture: str
    record_types: Mapping[str, int]
    warnings: tuple[str, ...] = ()
    schema_version: int = _BATCH_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "files", tuple(self.files))
        object.__setattr__(
            self,
            "record_types",
            MappingProxyType(dict(sorted(self.record_types.items()))),
        )
        object.__setattr__(self, "warnings", tuple(self.warnings))

    @property
    def selected(self) -> int:
        return len(self.files)

    @property
    def decoded(self) -> int:
        return sum(item.status == BatchDecodeStatus.DECODED for item in self.files)

    @property
    def unsupported(self) -> int:
        return sum(item.status == BatchDecodeStatus.UNSUPPORTED for item in self.files)

    @property
    def failed(self) -> int:
        return sum(item.status == BatchDecodeStatus.FAILED for item in self.files)

    @property
    def record_count(self) -> int:
        return sum(item.record_count for item in self.files)

    @property
    def ok(self) -> bool:
        return self.failed == 0

    def to_jsonable(self) -> dict[str, object]:
        return {
            "kind": _BATCH_SUMMARY_KIND,
            "schema_version": self.schema_version,
            "mode": self.mode,
            "summary_path": self.summary_path.relative_to(self.output_root).as_posix(),
            "platform": self.platform,
            "architecture": self.architecture,
            "protocol_version": self.protocol_version,
            "sdk_commit": self.sdk_commit,
            "decoder_version": self.decoder_version,
            "selected": self.selected,
            "decoded": self.decoded,
            "unsupported": self.unsupported,
            "failed": self.failed,
            "record_count": self.record_count,
            "record_types": dict(self.record_types),
            "warnings": list(self.warnings),
            "files": [item.to_jsonable() for item in self.files],
        }


@dataclass(frozen=True)
class _Selection:
    source: Path
    relative: PurePosixPath
    destination: Path
    source_sha256: str
    secret_id: str | None = None


def _digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as current:
        for block in iter(lambda: current.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def _resolved_input_root(value: os.PathLike[str] | str) -> Path:
    raw = Path(value).expanduser()
    if raw.is_symlink():
        raise DecoderManifestError("REC source root must not be a symbolic link.")
    root = raw.resolve()
    if not root.is_dir():
        raise DecoderManifestError("REC source root must be a directory.")
    return root


def _resolved_output_root(value: os.PathLike[str] | str) -> Path:
    raw = Path(value).expanduser().absolute()
    for candidate in (raw, *raw.parents):
        if candidate.exists():
            if candidate.is_symlink():
                raise DecoderManifestError("REC output root must not traverse a symbolic link.")
            if candidate == raw and not candidate.is_dir():
                raise DecoderManifestError("REC output root must be a directory.")
    return raw.resolve(strict=False)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _source_is_safe(source: Path, root: Path) -> bool:
    if not source.is_file() or source.is_symlink() or not os.access(source, os.R_OK):
        return False
    try:
        relative = source.relative_to(root)
    except ValueError:
        return False
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            return False
    return _is_relative_to(source.resolve(), root)


def _destination_for(output_root: Path, relative: PurePosixPath) -> Path:
    return output_root.joinpath(*relative.with_suffix(".jsonl").parts)


def _tree_selections(source_root: Path, output_root: Path) -> tuple[_Selection, ...]:
    selected: list[tuple[PurePosixPath, Path]] = []
    for current, directories, files in os.walk(source_root, followlinks=False):
        current_path = Path(current)
        directories[:] = sorted(
            name
            for name in directories
            if not (current_path / name).is_symlink()
            and not _is_relative_to((current_path / name).resolve(strict=False), output_root)
        )
        for name in sorted(files):
            source = current_path / name
            if source.suffix.lower() != ".rec" or not _source_is_safe(source, source_root):
                continue
            resolved = source.resolve()
            if _is_relative_to(resolved, output_root):
                continue
            selected.append(
                (
                    PurePosixPath(source.relative_to(source_root).as_posix()),
                    resolved,
                )
            )
    return tuple(
        _Selection(
            source,
            relative,
            _destination_for(output_root, relative),
            _digest(source),
        )
        for relative, source in sorted(selected, key=lambda item: item[0].as_posix())
    )


def _strict_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _manifest_row(line: bytes, line_number: int) -> dict[str, object]:
    if len(line) > _MAX_MANIFEST_LINE_BYTES:
        raise DecoderManifestError(f"REC manifest row {line_number} exceeds the size limit.")
    try:
        value = json.loads(line, object_pairs_hook=_strict_object)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise DecoderManifestError(f"REC manifest row {line_number} is invalid JSON.") from exc
    if not isinstance(value, dict):
        raise DecoderManifestError(f"REC manifest row {line_number} is not an object.")
    if not set(value).issubset(_MANIFEST_FIELDS):
        raise DecoderManifestError(f"REC manifest row {line_number} has unknown fields.")
    if (
        not isinstance(value.get("schema_version"), int)
        or isinstance(value.get("schema_version"), bool)
        or value.get("schema_version") != _BATCH_SCHEMA_VERSION
    ):
        raise DecoderManifestError(
            f"REC manifest row {line_number} has an unsupported schema version."
        )
    return value


def _relative_source(value: object, line_number: int) -> PurePosixPath:
    if (
        not isinstance(value, str)
        or not value
        or "\\" in value
        or any(not part for part in value.split("/"))
    ):
        raise DecoderManifestError(f"REC manifest row {line_number} has an invalid source path.")
    relative = PurePosixPath(value)
    if (
        relative.is_absolute()
        or any(part in {"", ".", ".."} for part in relative.parts)
        or relative.suffix.lower() != ".rec"
    ):
        raise DecoderManifestError(f"REC manifest row {line_number} has an invalid source path.")
    return relative


def _manifest_selections(
    manifest_path: Path, source_root: Path, output_root: Path
) -> tuple[_Selection, ...]:
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise DecoderManifestError("REC decode manifest must be a regular file.")
    try:
        payload = manifest_path.read_bytes()
    except OSError as exc:
        raise DecoderManifestError("REC decode manifest could not be read.") from exc
    if payload and not payload.endswith(b"\n"):
        raise DecoderManifestError("REC decode manifest must end with a newline.")
    selections: list[_Selection] = []
    sources: set[str] = set()
    destinations: set[Path] = set()
    for line_number, line in enumerate(payload.splitlines(), start=1):
        if not line.strip():
            continue
        row = _manifest_row(line, line_number)
        relative = _relative_source(row.get("source"), line_number)
        relative_text = relative.as_posix()
        if relative_text in sources:
            raise DecoderManifestError("REC decode manifest contains duplicate sources.")
        source = source_root.joinpath(*relative.parts)
        if not _source_is_safe(source, source_root):
            raise DecoderManifestError(f"REC manifest source is missing or unsafe: {relative_text}")
        source = source.resolve()
        digest = _digest(source)
        expected_digest = row.get("source_sha256")
        if expected_digest is not None and (
            not isinstance(expected_digest, str)
            or not _DIGEST_RE.fullmatch(expected_digest)
            or expected_digest != digest
        ):
            raise DecoderManifestError(
                f"REC manifest source digest does not match: {relative_text}"
            )
        secret_id = row.get("secret_id")
        if secret_id is not None and (
            not isinstance(secret_id, str) or not secret_id or len(secret_id) > 256
        ):
            raise DecoderManifestError(f"REC manifest row {line_number} has an invalid secret_id.")
        destination = _destination_for(output_root, relative)
        if destination in destinations:
            raise DecoderManifestError("REC decode manifest derives duplicate destinations.")
        sources.add(relative_text)
        destinations.add(destination)
        selections.append(_Selection(source, relative, destination, digest, secret_id))
    return tuple(sorted(selections, key=lambda item: item.relative.as_posix()))


def _validate_existing_summary(path: Path) -> None:
    if not path.is_file() or path.is_symlink():
        raise DecoderManifestError("Overwrite requires an existing project-owned batch summary.")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DecoderManifestError(
            "Overwrite requires an existing project-owned batch summary."
        ) from exc
    if (
        not isinstance(value, dict)
        or value.get("kind") != _BATCH_SUMMARY_KIND
        or value.get("schema_version") != _BATCH_SCHEMA_VERSION
    ):
        raise DecoderManifestError("Overwrite requires an existing project-owned batch summary.")


def _validate_destination_parent(destination: Path, output_root: Path) -> None:
    relative = destination.relative_to(output_root)
    current = output_root
    for part in relative.parent.parts:
        current /= part
        if current.exists() and (current.is_symlink() or not current.is_dir()):
            raise DecoderManifestError("REC batch destination parent is unsafe or not a directory.")


def _preflight(
    selections: tuple[_Selection, ...],
    source_root: Path,
    output_root: Path,
    *,
    overwrite: bool,
) -> Path:
    if source_root == output_root or _is_relative_to(source_root, output_root):
        raise DecoderManifestError("REC output root must not contain the source root.")
    summary = output_root / "summary.json"
    destinations: set[Path] = set()
    for selection in selections:
        destination = selection.destination
        if destination in destinations:
            raise DecoderManifestError("REC batch derives duplicate destinations.")
        destinations.add(destination)
        if not _is_relative_to(destination, output_root):
            raise DecoderManifestError("REC batch destination escapes its output root.")
        if destination.resolve(strict=False) == selection.source:
            raise DecoderManifestError("REC batch destination aliases its source.")
        _validate_destination_parent(destination, output_root)
        if not destination.exists():
            continue
        if os.path.samefile(selection.source, destination):
            raise DecoderManifestError("REC batch destination aliases its source.")
        if not overwrite:
            raise DecoderManifestError(
                f"REC batch destination already exists: {selection.relative.as_posix()}"
            )
        try:
            for _record in iter_decoded_records(destination):
                pass
        except DecoderProtocolError as exc:
            raise DecoderManifestError(
                "Overwrite requires project-owned decoded JSONL destinations."
            ) from exc
    if summary.exists():
        if not overwrite:
            raise DecoderManifestError("REC batch summary already exists.")
        _validate_existing_summary(summary)
    return summary


def _error_code(error: RecDecodeError) -> str:
    if isinstance(error, UnsupportedRecordingError):
        return "unsupported_recording"
    if isinstance(error, DecoderProtocolError):
        return "protocol_error"
    if isinstance(error, RecordingDecodeError):
        return "decode_failed"
    return "decoder_unavailable"


def _redacted_error(
    error: RecDecodeError,
    selection: _Selection,
    source_root: Path,
    output_root: Path,
) -> str:
    message = str(error)
    for private, replacement in (
        (str(selection.source), selection.relative.as_posix()),
        (str(source_root), "<source-root>"),
        (str(output_root), "<output-root>"),
    ):
        message = message.replace(private, replacement)
    return message


def _result_from_report(
    selection: _Selection, output_root: Path, report: DecodeReport
) -> BatchFileResult:
    record_type = next(iter(report.record_types)) if len(report.record_types) == 1 else None
    return BatchFileResult(
        BatchDecodeStatus.DECODED,
        selection.relative.as_posix(),
        selection.destination.relative_to(output_root).as_posix(),
        report.source_sha256,
        report.destination_sha256,
        record_type,
        report.record_count,
        report.record_types,
        report.warnings,
    )


def _write_summary(path: Path, payload: dict[str, object], *, overwrite: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=".summary.",
            suffix=".json",
            delete=False,
        ) as temporary:
            json.dump(payload, temporary, indent=2, sort_keys=True)
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        if overwrite:
            os.replace(temporary_path, path)
        else:
            try:
                os.link(temporary_path, path)
            except FileExistsError as exc:
                raise DecoderManifestError("REC batch summary already exists.") from exc
            temporary_path.unlink()
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _decode_batch(
    mode: str,
    source_root: Path,
    output_root: Path,
    selections: tuple[_Selection, ...],
    *,
    overwrite: bool,
    timeout_seconds: float | None,
) -> BatchDecodeReport:
    if timeout_seconds is not None and timeout_seconds <= 0:
        raise DecoderManifestError("timeout_seconds must be positive.")
    if any(selection.secret_id is not None for selection in selections):
        raise DecoderManifestError(
            "secret_id requires the protected protocol and a configured secret provider."
        )
    summary_path = _preflight(selections, source_root, output_root, overwrite=overwrite)
    files: list[BatchFileResult] = []
    sdk_commit: str | None = None
    decoder_version: str | None = None
    counts: dict[str, int] = {}
    for selection in selections:
        try:
            decoded = decode_recording(
                selection.source,
                selection.destination,
                overwrite=overwrite,
                timeout_seconds=timeout_seconds,
            )
        except UnsupportedRecordingError as exc:
            files.append(
                BatchFileResult(
                    BatchDecodeStatus.UNSUPPORTED,
                    selection.relative.as_posix(),
                    selection.destination.relative_to(output_root).as_posix(),
                    selection.source_sha256,
                    error_code=_error_code(exc),
                    error=_redacted_error(exc, selection, source_root, output_root),
                )
            )
            continue
        except RecDecodeError as exc:
            files.append(
                BatchFileResult(
                    BatchDecodeStatus.FAILED,
                    selection.relative.as_posix(),
                    selection.destination.relative_to(output_root).as_posix(),
                    selection.source_sha256,
                    error_code=_error_code(exc),
                    error=_redacted_error(exc, selection, source_root, output_root),
                )
            )
            continue
        files.append(_result_from_report(selection, output_root, decoded))
        sdk_commit = sdk_commit or decoded.sdk_commit
        decoder_version = decoder_version or decoded.decoder_version
        for record_type, count in decoded.record_types.items():
            counts[record_type] = counts.get(record_type, 0) + count
    report = BatchDecodeReport(
        mode,
        source_root,
        output_root,
        summary_path,
        tuple(files),
        sdk_commit,
        decoder_version,
        1,
        normalized_platform(),
        normalized_architecture(),
        counts,
    )
    _write_summary(summary_path, report.to_jsonable(), overwrite=overwrite)
    return report


def decode_recording_tree(
    source_root: os.PathLike[str] | str,
    output_root: os.PathLike[str] | str,
    *,
    overwrite: bool = False,
    timeout_seconds: float | None = None,
) -> BatchDecodeReport:
    """Decode a deterministic, symlink-free tree of regular REC files."""
    source = _resolved_input_root(source_root)
    output = _resolved_output_root(output_root)
    selections = _tree_selections(source, output)
    return _decode_batch(
        "tree",
        source,
        output,
        selections,
        overwrite=overwrite,
        timeout_seconds=timeout_seconds,
    )


def decode_recording_manifest(
    manifest: os.PathLike[str] | str,
    source_root: os.PathLike[str] | str,
    output_root: os.PathLike[str] | str,
    *,
    overwrite: bool = False,
    timeout_seconds: float | None = None,
) -> BatchDecodeReport:
    """Decode a strict schema-versioned manifest of root-relative REC files."""
    source = _resolved_input_root(source_root)
    output = _resolved_output_root(output_root)
    selections = _manifest_selections(Path(manifest).expanduser(), source, output)
    return _decode_batch(
        "manifest",
        source,
        output,
        selections,
        overwrite=overwrite,
        timeout_seconds=timeout_seconds,
    )


__all__ = [
    "BatchDecodeReport",
    "BatchDecodeStatus",
    "BatchFileResult",
    "decode_recording_manifest",
    "decode_recording_tree",
]
