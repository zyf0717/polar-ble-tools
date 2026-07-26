"""Validated local decoding of Polar offline recording files."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import signal
import subprocess
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from typing import Any

from polar_ble_tools.schemas.cache import SdkCache
from polar_ble_tools.sdk_tools.decoder.toolchain import java_environment
from polar_ble_tools.sdk_tools.revisions import require_full_commit, require_within

_PROTOCOL_VERSION = 1
_MAX_DIAGNOSTIC = 8_192
_MAX_STATUS_BYTES = 8_192
_MAX_JSONL_LINE_BYTES = 1_048_576
_RUNTIME_LAUNCHERS = frozenset({"bin/polar-rec-decoder", "bin/polar-rec-decoder.bat"})
_COMMIT_RE = re.compile(r"[0-9a-f]{40}")
_DIGEST_RE = re.compile(r"[0-9a-f]{64}")
_RECORD_TYPE_RE = re.compile(r"[a-z][a-z0-9_]*")


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


@dataclass(frozen=True)
class _Decoder:
    executable: Path
    manifest: Mapping[str, object]


def _decoder_environment(cache: SdkCache, manifest: Mapping[str, object]) -> dict[str, str]:
    runtime = manifest.get("runtime")
    if not isinstance(runtime, dict):
        raise DecoderManifestError(
            "Decoder manifest has no runtime descriptor; rebuild the decoder."
        )
    platform_name = runtime.get("platform")
    architecture = runtime.get("architecture")
    version = runtime.get("java_version")
    relative = runtime.get("java_relative_cache_path")
    expected_digest = runtime.get("java_executable_sha256")
    expected_platform = platform.system().lower()
    expected_architecture = platform.machine().lower().replace("amd64", "x86_64")
    if platform_name != expected_platform or architecture != expected_architecture:
        raise DecoderUnavailableError(
            "Active REC decoder was built for a different platform or architecture."
        )
    if not all(isinstance(value, str) for value in (version, relative, expected_digest)):
        raise DecoderManifestError("Decoder runtime descriptor is malformed.")
    if len(expected_digest) != 64 or any(
        character not in "0123456789abcdef" for character in expected_digest
    ):
        raise DecoderManifestError("Decoder runtime descriptor has an invalid JDK digest.")
    try:
        java_home = require_within(cache.root / relative, cache.root)
    except ValueError as exc:
        raise DecoderManifestError("Decoder runtime descriptor escapes the cache root.") from exc
    expected_home = cache.rec_jvm_java_home(platform_name, architecture, version).resolve()
    if java_home != expected_home:
        raise DecoderManifestError(
            "Decoder runtime descriptor does not name the pinned JDK location."
        )
    executable = java_home / "bin" / "java"
    if not executable.is_file() or executable.is_symlink() or not os.access(executable, os.X_OK):
        raise DecoderUnavailableError(
            "Decoder JDK is missing or not executable; rebuild the active REC decoder."
        )
    if _digest(executable) != expected_digest:
        raise DecoderVerificationError(
            "Decoder JDK changed; rebuild and verify the active REC decoder."
        )
    try:
        return java_environment(java_home)
    except RuntimeError as exc:
        raise DecoderUnavailableError(str(exc)) from exc


def _digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as current:
        for block in iter(lambda: current.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def _within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _runtime_file_digests(root: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_dir() or path.name == "manifest.json":
            continue
        if path.is_symlink() or not path.is_file():
            raise DecoderManifestError(f"Decoder runtime has an unsafe entry: {path.name}")
        relative = path.relative_to(root).as_posix()
        allowed = relative in _RUNTIME_LAUNCHERS or (
            relative.startswith("lib/") and "/" not in relative[4:] and relative.endswith(".jar")
        )
        if not allowed:
            raise DecoderManifestError(f"Decoder runtime has an unexpected file: {relative}")
        files[relative] = _digest(path)
    return files


def _recover_interrupted_promotion(cache: SdkCache, commit: str) -> Path:
    try:
        commit = require_full_commit(commit)
        root = require_within(cache.decoder_path(commit), cache.decoder_root)
    except ValueError as exc:
        raise DecoderManifestError(str(exc)) from exc
    if root.exists():
        return root
    backups = sorted(
        path
        for path in cache.decoder_root.glob(f".{commit}.previous-*")
        if path.is_dir() and not path.is_symlink()
    )
    if len(backups) == 1:
        backups[0].replace(root)
        return root
    if backups:
        raise DecoderManifestError("Interrupted decoder promotion has ambiguous recovery entries.")
    return root


def _load_decoder(cache: SdkCache) -> _Decoder:
    active = cache.active_decoder_manifest_path
    if not active.is_file():
        raise DecoderUnavailableError(
            "No active REC decoder. Build one with: polar-ble sdk decoder build"
        )
    try:
        active_payload = json.loads(active.read_text(encoding="utf-8"))
        commit = active_payload["sdk_commit"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise DecoderManifestError(f"Invalid active decoder manifest at {active}.") from exc
    try:
        commit = require_full_commit(commit)
    except ValueError as exc:
        raise DecoderManifestError("Active decoder manifest has an invalid SDK commit.") from exc
    root = _recover_interrupted_promotion(cache, commit)
    manifest_path = root / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        relative = manifest["executable_relative_path"]
        expected_digest = manifest["executable_sha256"]
        expected_runtime_files = manifest["runtime_files"]
        runtime = manifest["runtime"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise DecoderManifestError(f"Invalid decoder manifest at {manifest_path}.") from exc
    if (
        manifest.get("manifest_version") != 1
        or manifest.get("sdk_commit") != commit
        or manifest.get("decoder_protocol_version") != _PROTOCOL_VERSION
        or manifest.get("verified") is not True
        or not isinstance(relative, str)
        or not isinstance(expected_digest, str)
        or not isinstance(expected_runtime_files, dict)
        or not isinstance(runtime, dict)
        or not all(
            isinstance(path, str) and isinstance(digest, str)
            for path, digest in expected_runtime_files.items()
        )
    ):
        raise DecoderManifestError(
            "Decoder manifest does not describe a verified protocol-v1 decoder."
        )
    executable = (root / relative).resolve()
    if (
        not _within(executable, root)
        or not executable.is_file()
        or executable.is_symlink()
        or not os.access(executable, os.X_OK)
    ):
        raise DecoderManifestError("Decoder executable is missing or escapes its cache directory.")
    if _digest(executable) != expected_digest:
        raise DecoderVerificationError(
            "Decoder executable digest changed; rebuild and verify the decoder."
        )
    if _runtime_file_digests(root) != expected_runtime_files:
        raise DecoderVerificationError(
            "Decoder runtime files changed; rebuild and verify the decoder."
        )
    return _Decoder(executable, manifest)


def _handshake(decoder: _Decoder, environment: Mapping[str, str], command: str) -> None:
    returncode, stdout, stderr = _run_sidecar(
        [str(decoder.executable), command], environment=environment, timeout_seconds=30
    )
    try:
        status = json.loads(stdout)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DecoderProtocolError("REC decoder returned malformed handshake JSON.") from exc
    expected_version = decoder.manifest.get("decoder_version")
    if (
        returncode != 0
        or not isinstance(status, dict)
        or status.get("status") != "ok"
        or status.get("protocol_version") != _PROTOCOL_VERSION
        or status.get("sdk_commit") != decoder.manifest["sdk_commit"]
        or not isinstance(expected_version, str)
        or status.get("decoder_version") != expected_version
    ):
        raise DecoderVerificationError(
            f"REC decoder {command} handshake failed: {_diagnostic(stderr)}"
        )


def _verified_decoder(cache: SdkCache, *, self_test: bool) -> _Decoder:
    decoder = _load_decoder(cache)
    environment = _decoder_environment(cache, decoder.manifest)
    _handshake(decoder, environment, "version")
    if self_test:
        _handshake(decoder, environment, "self-test")
    return decoder


def decoder_status(*, cache: SdkCache | None = None) -> DecoderStatus:
    try:
        decoder = _verified_decoder(cache or SdkCache.default(), self_test=False)
    except (RecDecodeError, OSError, subprocess.SubprocessError) as exc:
        return DecoderStatus(False, False, None, None, None, str(exc))
    manifest = decoder.manifest
    return DecoderStatus(
        True,
        True,
        str(manifest["sdk_commit"]),
        int(manifest["decoder_protocol_version"]),
        str(manifest.get("verification_level", "handshake")),
        None,
    )


def verify_active_decoder(*, cache: SdkCache | None = None) -> bool:
    """Execute both sidecar handshakes for the active decoder."""
    _verified_decoder(cache or SdkCache.default(), self_test=True)
    return True


def _diagnostic(value: str | bytes | None) -> str:
    if not value:
        return "no diagnostic output"
    text = value.decode("utf-8", "replace") if isinstance(value, bytes) else value
    return text.strip()[:_MAX_DIAGNOSTIC]


def _drain_stream(stream, limit: int, sink: list[bytes | bool]) -> None:
    payload = bytearray()
    exceeded = False
    while chunk := stream.read(8_192):
        remaining = limit - len(payload)
        if remaining > 0:
            payload.extend(chunk[:remaining])
        exceeded = exceeded or len(chunk) > remaining
    sink.extend((bytes(payload), exceeded))


def _run_sidecar(
    command: list[str], *, environment: Mapping[str, str], timeout_seconds: float
) -> tuple[int, bytes, bytes]:
    process = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environment,
        start_new_session=os.name == "posix",
    )
    assert process.stdout is not None and process.stderr is not None
    stdout: list[bytes | bool] = []
    stderr: list[bytes | bool] = []
    stdout_thread = Thread(
        target=_drain_stream, args=(process.stdout, _MAX_STATUS_BYTES, stdout), daemon=True
    )
    stderr_thread = Thread(
        target=_drain_stream, args=(process.stderr, _MAX_DIAGNOSTIC, stderr), daemon=True
    )
    stdout_thread.start()
    stderr_thread.start()
    try:
        returncode = process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
            process.wait(timeout=2)
        raise DecoderTimeoutError("REC decoder timed out; retry with a larger timeout.") from exc
    finally:
        stdout_thread.join(timeout=2)
        stderr_thread.join(timeout=2)
    if stdout_thread.is_alive() or stderr_thread.is_alive():
        raise DecoderProtocolError("REC decoder did not close its diagnostic streams.")
    stdout_payload, stdout_exceeded = stdout
    stderr_payload, _ = stderr
    if stdout_exceeded:
        raise DecoderProtocolError("REC decoder status exceeded the maximum size.")
    return returncode, stdout_payload, stderr_payload


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


def _iter_json_rows(path: Path) -> Iterator[tuple[int, dict[str, Any]]]:
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
        or header.get("protocol_version") != _PROTOCOL_VERSION
        or header.get("source_sha256") != source_digest
        or not isinstance(header.get("decoder_version"), str)
        or not header["decoder_version"]
        or not isinstance(header.get("sdk_commit"), str)
        or not _COMMIT_RE.fullmatch(header["sdk_commit"])
        or not isinstance(header.get("source_sha256"), str)
        or not _DIGEST_RE.fullmatch(header["source_sha256"])
    ):
        raise DecoderProtocolError("Decoder output has an invalid protocol header.")


def _validated_rows(path: Path, source_digest: str) -> tuple[dict[str, Any], dict[str, Any]]:
    header: dict[str, Any] | None = None
    summary: dict[str, Any] | None = None
    counts: dict[str, int] = {}
    record_count = 0
    for line_number, record in _iter_json_rows(path):
        if header is None:
            _validate_header(record, source_digest)
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


def decode_recording(
    source: os.PathLike[str] | str,
    destination: os.PathLike[str] | str,
    *,
    overwrite: bool = False,
    timeout_seconds: float | None = None,
) -> DecodeReport:
    source_path, destination_path = (
        Path(source).expanduser().resolve(),
        Path(destination).expanduser(),
    )
    if not source_path.is_file() or source_path.is_symlink() or not os.access(source_path, os.R_OK):
        raise RecordingDecodeError("Input must be a readable, regular .REC file.")
    if destination_path.exists() and not overwrite:
        raise RecordingDecodeError(
            f"Output already exists: {destination_path}; pass overwrite=True to replace it."
        )
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    if not destination_path.parent.is_dir():
        raise RecordingDecodeError("Output parent is not a directory.")
    if timeout_seconds is not None and timeout_seconds <= 0:
        raise RecordingDecodeError("timeout_seconds must be positive.")
    cache = SdkCache.default()
    decoder = _verified_decoder(cache, self_test=False)
    source_digest = _digest(source_path)
    with TemporaryDirectory(
        prefix=f".{destination_path.name}.", dir=destination_path.parent
    ) as directory:
        temporary = Path(directory) / "decoded.jsonl"
        try:
            returncode, stdout, stderr = _run_sidecar(
                [
                    str(decoder.executable),
                    "decode",
                    "--input",
                    str(source_path),
                    "--output",
                    str(temporary),
                    "--protocol",
                    "1",
                ],
                environment=_decoder_environment(cache, decoder.manifest),
                timeout_seconds=timeout_seconds or 120,
            )
        except OSError as exc:
            raise RecordingDecodeError(f"REC decoder could not start: {exc}") from exc
        try:
            status = json.loads(stdout)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DecoderProtocolError("REC decoder returned malformed status JSON.") from exc
        if not isinstance(status, dict) or not isinstance(status.get("status"), str):
            raise DecoderProtocolError("REC decoder returned an invalid status object.")
        if returncode:
            if status.get("status") != "error":
                raise DecoderProtocolError("REC decoder failed without an error status object.")
            raise RecordingDecodeError(f"REC decoder failed: {_diagnostic(stderr)}")
        header, summary = _validated_rows(temporary, source_digest)
        if status.get("status") != "ok" or status.get("record_count") != summary["record_count"]:
            raise DecoderProtocolError("REC decoder status disagrees with the decoded stream.")
        if header.get("sdk_commit") != decoder.manifest["sdk_commit"]:
            raise DecoderProtocolError(
                "REC decoder SDK provenance differs from its verified manifest."
            )
        if overwrite:
            os.replace(temporary, destination_path)
        else:
            try:
                os.link(temporary, destination_path)
            except FileExistsError as exc:
                raise RecordingDecodeError(
                    f"Output already exists: {destination_path}; pass overwrite=True to replace it."
                ) from exc
            temporary.unlink()
    return DecodeReport(
        source_path=source_path,
        destination_path=destination_path.resolve(),
        source_sha256=source_digest,
        destination_sha256=_digest(destination_path),
        sdk_commit=str(header["sdk_commit"]),
        decoder_version=str(header["decoder_version"]),
        record_count=int(summary["record_count"]),
        record_types=dict(summary["record_types"]),
        warnings=tuple(str(item) for item in summary["warnings"]),
    )


def iter_decoded_records(decoded_jsonl: os.PathLike[str] | str) -> Iterator[RecRecord]:
    path = Path(decoded_jsonl)
    try:
        _, header = next(_iter_json_rows(path))
        source_digest = header["source_sha256"]
    except (StopIteration, KeyError, DecoderProtocolError) as exc:
        raise DecoderProtocolError("Decoded JSONL is missing a valid header.") from exc
    if not isinstance(source_digest, str):
        raise DecoderProtocolError("Decoded JSONL has an invalid source digest.")
    _validated_rows(path, source_digest)
    for _, row in _iter_json_rows(path):
        if row.get("type") == "record":
            yield RecRecord(row["record_type"], row["timestamp_ns"], dict(row["payload"]))


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
    "decode_recording",
    "decoder_status",
    "iter_decoded_records",
]
