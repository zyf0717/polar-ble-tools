"""Validated local decoding of Polar offline recording files."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Thread
from typing import Any

from polar_ble_tools.schemas.cache import SdkCache

_PROTOCOL_VERSION = 1
_MAX_DIAGNOSTIC = 8_192
_MAX_STATUS_BYTES = 8_192
_RUNTIME_LAUNCHERS = frozenset({"bin/polar-rec-decoder", "bin/polar-rec-decoder.bat"})


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


def _decoder_environment(cache: SdkCache, sdk_commit: str) -> dict[str, str]:
    java_home = cache.decoder_build_path(sdk_commit) / "tools" / "jdk-21.0.12+8"
    if not (java_home / "bin" / "java").is_file():
        raise DecoderUnavailableError("Decoder JDK is missing; rebuild the active REC decoder.")
    environment = os.environ.copy()
    environment["JAVA_HOME"] = str(java_home)
    environment["PATH"] = f"{java_home / 'bin'}:{environment.get('PATH', '')}"
    return environment


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
    if not isinstance(commit, str) or len(commit) != 40:
        raise DecoderManifestError("Active decoder manifest has an invalid SDK commit.")
    root = cache.decoder_path(commit)
    manifest_path = root / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        relative = manifest["executable_relative_path"]
        expected_digest = manifest["executable_sha256"]
        expected_runtime_files = manifest["runtime_files"]
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
        or not all(isinstance(path, str) and isinstance(digest, str) for path, digest in expected_runtime_files.items())
    ):
        raise DecoderManifestError("Decoder manifest does not describe a verified protocol-v1 decoder.")
    executable = (root / relative).resolve()
    if not _within(executable, root) or not executable.is_file() or executable.is_symlink():
        raise DecoderManifestError("Decoder executable is missing or escapes its cache directory.")
    if _digest(executable) != expected_digest:
        raise DecoderVerificationError("Decoder executable digest changed; rebuild and verify the decoder.")
    if _runtime_file_digests(root) != expected_runtime_files:
        raise DecoderVerificationError("Decoder runtime files changed; rebuild and verify the decoder.")
    return _Decoder(executable, manifest)


def decoder_status(*, cache: SdkCache | None = None) -> DecoderStatus:
    try:
        decoder = _load_decoder(cache or SdkCache.default())
    except RecDecodeError as exc:
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


def _run_sidecar(command: list[str], *, environment: Mapping[str, str], timeout_seconds: float) -> tuple[int, bytes, bytes]:
    process = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environment,
    )
    assert process.stdout is not None and process.stderr is not None
    stdout: list[bytes | bool] = []
    stderr: list[bytes | bool] = []
    stdout_thread = Thread(target=_drain_stream, args=(process.stdout, _MAX_STATUS_BYTES, stdout))
    stderr_thread = Thread(target=_drain_stream, args=(process.stderr, _MAX_DIAGNOSTIC, stderr))
    stdout_thread.start()
    stderr_thread.start()
    try:
        returncode = process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        process.kill()
        process.wait()
        raise DecoderTimeoutError("REC decoder timed out; retry with a larger timeout.") from exc
    finally:
        stdout_thread.join()
        stderr_thread.join()
    stdout_payload, stdout_exceeded = stdout
    stderr_payload, _ = stderr
    if stdout_exceeded:
        raise DecoderProtocolError("REC decoder status exceeded the maximum size.")
    return returncode, stdout_payload, stderr_payload


def _validated_rows(path: Path, source_digest: str) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DecoderProtocolError("Decoder output is not valid UTF-8 JSON Lines.") from exc
    if len(rows) < 2 or not isinstance(rows[0], dict) or not isinstance(rows[-1], dict):
        raise DecoderProtocolError("Decoder output is missing protocol header or summary.")
    header, summary = rows[0], rows[-1]
    if header.get("type") != "header" or summary.get("type") != "summary":
        raise DecoderProtocolError("Decoder output has invalid header or summary ordering.")
    if header.get("protocol_version") != _PROTOCOL_VERSION or header.get("source_sha256") != source_digest:
        raise DecoderProtocolError("Decoder output does not match protocol v1 or the requested source.")
    records = rows[1:-1]
    counts: dict[str, int] = {}
    for record in records:
        if not isinstance(record, dict) or record.get("type") != "record":
            raise DecoderProtocolError("Decoder output contains an invalid record.")
        record_type, timestamp, payload = record.get("record_type"), record.get("timestamp_ns"), record.get("payload")
        if not isinstance(record_type, str) or record_type != record_type.lower() or not isinstance(payload, dict):
            raise DecoderProtocolError("Decoder record has an invalid envelope.")
        if timestamp is not None and (not isinstance(timestamp, int) or isinstance(timestamp, bool)):
            raise DecoderProtocolError("Decoder record timestamp is invalid.")
        counts[record_type] = counts.get(record_type, 0) + 1
    if summary.get("record_count") != len(records) or summary.get("record_types") != counts:
        raise DecoderProtocolError("Decoder summary does not match its record stream.")
    if not isinstance(summary.get("warnings"), list):
        raise DecoderProtocolError("Decoder summary warnings are invalid.")
    return header, summary


def decode_recording(
    source: os.PathLike[str] | str,
    destination: os.PathLike[str] | str,
    *,
    overwrite: bool = False,
    timeout_seconds: float | None = None,
) -> DecodeReport:
    source_path, destination_path = Path(source).expanduser().resolve(), Path(destination).expanduser()
    if not source_path.is_file() or source_path.is_symlink() or not os.access(source_path, os.R_OK):
        raise RecordingDecodeError("Input must be a readable, regular .REC file.")
    if destination_path.exists() and not overwrite:
        raise RecordingDecodeError(f"Output already exists: {destination_path}; pass overwrite=True to replace it.")
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    if not destination_path.parent.is_dir():
        raise RecordingDecodeError("Output parent is not a directory.")
    if timeout_seconds is not None and timeout_seconds <= 0:
        raise RecordingDecodeError("timeout_seconds must be positive.")
    cache = SdkCache.default()
    decoder = _load_decoder(cache)
    source_digest = _digest(source_path)
    with NamedTemporaryFile(prefix=f".{destination_path.name}.", suffix=".jsonl", dir=destination_path.parent, delete=False) as output:
        temporary = Path(output.name)
    temporary.unlink()
    try:
        try:
            returncode, stdout, stderr = _run_sidecar(
                [str(decoder.executable), "decode", "--input", str(source_path), "--output", str(temporary), "--protocol", "1"],
                environment=_decoder_environment(cache, str(decoder.manifest["sdk_commit"])),
                timeout_seconds=timeout_seconds or 120,
            )
        except OSError as exc:
            raise RecordingDecodeError(f"REC decoder could not start: {exc}") from exc
        if returncode:
            raise RecordingDecodeError(f"REC decoder failed: {_diagnostic(stderr)}")
        try:
            status = json.loads(stdout)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DecoderProtocolError("REC decoder returned malformed status JSON.") from exc
        header, summary = _validated_rows(temporary, source_digest)
        if status.get("status") != "ok" or status.get("record_count") != summary["record_count"]:
            raise DecoderProtocolError("REC decoder status disagrees with the decoded stream.")
        if header.get("sdk_commit") != decoder.manifest["sdk_commit"]:
            raise DecoderProtocolError("REC decoder SDK provenance differs from its verified manifest.")
        temporary.replace(destination_path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
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
    source_digest = ""
    try:
        header = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
        source_digest = str(header["source_sha256"])
    except (OSError, IndexError, KeyError, json.JSONDecodeError) as exc:
        raise DecoderProtocolError("Decoded JSONL is missing a valid header.") from exc
    _validated_rows(path, source_digest)
    for line in path.read_text(encoding="utf-8").splitlines()[1:-1]:
        row = json.loads(line)
        yield RecRecord(row["record_type"], row["timestamp_ns"], dict(row["payload"]))


__all__ = [
    "DecodeReport", "DecoderManifestError", "DecoderProtocolError", "DecoderStatus",
    "DecoderTimeoutError", "DecoderUnavailableError", "DecoderVerificationError",
    "RecDecodeError", "RecRecord", "RecordingDecodeError", "decode_recording",
    "decoder_status", "iter_decoded_records",
]
