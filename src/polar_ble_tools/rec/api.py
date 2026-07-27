"""Validated local decoding of Polar offline recording files."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import subprocess
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from polar_ble_tools.rec.models import (
    DecodeReport,
    DecoderManifestError,
    DecoderProtocolError,
    DecoderStatus,
    DecoderTimeoutError,
    DecoderUnavailableError,
    DecoderVerificationError,
    RecDecodeError,
    RecordingDecodeError,
    RecRecord,
    UnsupportedRecordingError,
)
from polar_ble_tools.rec.process import diagnostic, run_sidecar
from polar_ble_tools.rec.publication import (
    preflight_destination,
    publish_decoded_output,
)
from polar_ble_tools.rec.validation import (
    PROTOCOL_VERSION,
    iter_json_rows,
    validated_rows,
)
from polar_ble_tools.schemas.cache import SdkCache
from polar_ble_tools.sdk_tools.decoder.errors import (
    LicenseNoticeMismatchError,
    LicenseNoticeMissingError,
    SdkLifecycleError,
)
from polar_ble_tools.sdk_tools.decoder.toolchain import (
    java_environment,
    normalized_architecture,
    normalized_platform,
    toolchain_descriptor,
    toolchain_descriptor_digest,
)
from polar_ble_tools.sdk_tools.decoder.toolchain import (
    java_home as toolchain_java_home,
)
from polar_ble_tools.sdk_tools.downloader import SDK_LICENSE_FILE, SDK_NOTICE_FILES
from polar_ble_tools.sdk_tools.revisions import require_full_commit, require_within

_RUNTIME_LAUNCHERS = frozenset({"bin/polar-rec-decoder", "bin/polar-rec-decoder.bat"})
_LICENSE_RELATIVE_PATH = f"licenses/{SDK_LICENSE_FILE}"
_NOTICE_RELATIVE_PATHS = {name: f"notices/{name}" for name in SDK_NOTICE_FILES}
_COMMIT_RE = re.compile(r"[0-9a-f]{40}")
_DIGEST_RE = re.compile(r"[0-9a-f]{64}")


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
    java_relative_path = runtime.get("java_relative_path")
    expected_digest = runtime.get("java_executable_sha256")
    descriptor_digest = runtime.get("toolchain_descriptor_sha256")
    expected_platform = normalized_platform(platform.system())
    expected_architecture = normalized_architecture(platform.machine())
    if platform_name != expected_platform or architecture != expected_architecture:
        raise DecoderUnavailableError(
            "Active REC decoder was built for a different platform or architecture; "
            "rebuild with: polar-ble sdk decoder build"
        )
    try:
        descriptor = toolchain_descriptor(expected_platform, expected_architecture)
    except RuntimeError as exc:
        raise DecoderUnavailableError(str(exc)) from exc
    if not all(
        isinstance(value, str)
        for value in (
            version,
            relative,
            java_relative_path,
            expected_digest,
            descriptor_digest,
        )
    ):
        raise DecoderManifestError("Decoder runtime descriptor is malformed.")
    if (
        version != descriptor.jdk_version
        or java_relative_path != descriptor.java_relative_path
        or descriptor_digest != toolchain_descriptor_digest(descriptor)
    ):
        raise DecoderVerificationError(
            "Decoder toolchain descriptor changed; rebuild with: polar-ble sdk decoder build"
        )
    if len(expected_digest) != 64 or any(
        character not in "0123456789abcdef" for character in expected_digest
    ):
        raise DecoderManifestError("Decoder runtime descriptor has an invalid JDK digest.")
    try:
        java_home = require_within(cache.root / relative, cache.root)
    except ValueError as exc:
        raise DecoderManifestError("Decoder runtime descriptor escapes the cache root.") from exc
    expected_home = toolchain_java_home(cache, descriptor).resolve()
    if java_home != expected_home:
        raise DecoderManifestError(
            "Decoder runtime descriptor does not name the pinned JDK location."
        )
    executable = java_home / java_relative_path
    if not executable.is_file() or executable.is_symlink() or not os.access(executable, os.X_OK):
        raise DecoderUnavailableError(
            "Decoder JDK is missing or not executable; rebuild the active REC decoder."
        )
    if _digest(executable) != expected_digest:
        raise DecoderVerificationError(
            "Decoder JDK changed; rebuild and verify the active REC decoder."
        )
    try:
        return java_environment(java_home, java_relative_path=java_relative_path)
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
        allowed = (
            relative in _RUNTIME_LAUNCHERS
            or relative == _LICENSE_RELATIVE_PATH
            or relative in _NOTICE_RELATIVE_PATHS.values()
            or (
                relative.startswith("lib/")
                and "/" not in relative[4:]
                and relative.endswith(".jar")
            )
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


def _verify_license_material(
    root: Path,
    manifest: Mapping[str, object],
    runtime_files: Mapping[str, object],
) -> None:
    source_digest = manifest.get("sdk_source_content_sha256")
    materials = manifest.get("license_material")
    if (
        not isinstance(source_digest, str)
        or not _DIGEST_RE.fullmatch(source_digest)
        or not isinstance(materials, list)
    ):
        raise LicenseNoticeMismatchError("Decoder licence/notice manifest is missing or malformed.")
    expected = {
        _LICENSE_RELATIVE_PATH: "license",
        **{relative: "notice" for relative in _NOTICE_RELATIVE_PATHS.values()},
    }
    actual: dict[str, Mapping[str, object]] = {}
    for item in materials:
        if not isinstance(item, dict) or set(item) != {
            "cache_relative_path",
            "kind",
            "sha256",
            "source_identity",
        }:
            raise LicenseNoticeMismatchError("Decoder licence/notice manifest is malformed.")
        relative = item.get("cache_relative_path")
        if not isinstance(relative, str) or relative in actual:
            raise LicenseNoticeMismatchError("Decoder licence/notice manifest has an invalid path.")
        actual[relative] = item
    if set(actual) != set(expected):
        raise LicenseNoticeMissingError(
            "Decoder cache is missing required licence or notice entries."
        )
    for relative, kind in expected.items():
        item = actual[relative]
        digest = item.get("sha256")
        if (
            item.get("kind") != kind
            or item.get("source_identity") != f"sha256:{source_digest}"
            or not isinstance(digest, str)
            or not _DIGEST_RE.fullmatch(digest)
            or runtime_files.get(relative) != digest
        ):
            raise LicenseNoticeMismatchError(
                "Decoder licence or notice provenance does not match its manifest."
            )
        candidate = root / relative
        path = candidate.resolve()
        if candidate.is_symlink() or not _within(path, root) or not path.is_file():
            raise LicenseNoticeMissingError(
                "Decoder cache is missing required licence or notice material."
            )
        if _digest(path) != digest:
            raise LicenseNoticeMismatchError(
                "Decoder licence or notice digest changed; rebuild the decoder."
            )


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
        or manifest.get("decoder_protocol_version") != PROTOCOL_VERSION
        or manifest.get("verified") is not True
        or manifest.get("platform") != runtime.get("platform")
        or manifest.get("architecture") != runtime.get("architecture")
        or manifest.get("java_version") != runtime.get("java_version")
        or manifest.get("toolchain_descriptor_sha256") != runtime.get("toolchain_descriptor_sha256")
        or not isinstance(manifest.get("gradle_version"), str)
        or not isinstance(manifest.get("polar_ble_tools_version"), str)
        or not isinstance(manifest.get("adapter_source_sha256"), str)
        or not _DIGEST_RE.fullmatch(str(manifest.get("adapter_source_sha256")))
        or not isinstance(manifest.get("java_archive_sha256"), str)
        or not _DIGEST_RE.fullmatch(str(manifest.get("java_archive_sha256")))
        or not isinstance(manifest.get("gradle_archive_sha256"), str)
        or not _DIGEST_RE.fullmatch(str(manifest.get("gradle_archive_sha256")))
        or not isinstance(manifest.get("toolchain_descriptor_sha256"), str)
        or not _DIGEST_RE.fullmatch(str(manifest.get("toolchain_descriptor_sha256")))
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
    _verify_license_material(root, manifest, expected_runtime_files)
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
    returncode, stdout, stderr = run_sidecar(
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
        or status.get("protocol_version") != PROTOCOL_VERSION
        or status.get("sdk_commit") != decoder.manifest["sdk_commit"]
        or not isinstance(expected_version, str)
        or status.get("decoder_version") != expected_version
    ):
        raise DecoderVerificationError(
            f"REC decoder {command} handshake failed: {diagnostic(stderr)}"
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
    except (RecDecodeError, SdkLifecycleError, OSError, subprocess.SubprocessError) as exc:
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
    preflight_destination(source_path, destination_path, overwrite=overwrite)
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
            returncode, stdout, stderr = run_sidecar(
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
            if status.get("error_code") == "unsupported_recording":
                raise UnsupportedRecordingError(
                    "The active official SDK parser does not support this recording."
                )
            raise RecordingDecodeError(f"REC decoder failed: {diagnostic(stderr)}")
        header, summary = validated_rows(temporary, source_digest)
        if status.get("status") != "ok" or status.get("record_count") != summary["record_count"]:
            raise DecoderProtocolError("REC decoder status disagrees with the decoded stream.")
        if header.get("sdk_commit") != decoder.manifest["sdk_commit"]:
            raise DecoderProtocolError(
                "REC decoder SDK provenance differs from its verified manifest."
            )
        publish_decoded_output(temporary, destination_path, overwrite=overwrite)
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
    validated_rows(path, None)
    for _, row in iter_json_rows(path):
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
    "UnsupportedRecordingError",
    "decode_recording",
    "decoder_status",
    "iter_decoded_records",
]
