"""Build and activate the optional, locally compiled REC decoder sidecar."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from polar_ble_tools import __version__
from polar_ble_tools.rec import DecoderManifestError, DecoderVerificationError, decoder_status
from polar_ble_tools.schemas.cache import SdkCache
from polar_ble_tools.sdk_tools.downloader import SUPPORTED_SDK_COMMIT, active_sdk_source


class DecoderBuildError(RuntimeError):
    """The local decoder could not be built or verified."""


@dataclass(frozen=True)
class DecoderBuildResult:
    sdk_commit: str
    decoder_path: Path
    activated: bool


def _digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as current:
        for block in iter(lambda: current.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def _write_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _adapter_digest() -> str:
    root = Path(__file__).parents[2] / "polar_ble_tools" / "sdk_tools" / "decoder_project"
    hasher = hashlib.sha256()
    for path in sorted(root.iterdir()):
        if path.is_file():
            hasher.update(path.name.encode("utf-8"))
            hasher.update(b"\0")
            hasher.update(path.read_bytes())
    return hasher.hexdigest()


def _run(
    command: list[str], *, timeout: float | None = None, environment: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            command, check=False, capture_output=True, text=True, timeout=timeout, env=environment
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DecoderBuildError(f"Decoder command failed: {exc}") from exc
    if completed.returncode:
        detail = (completed.stderr or completed.stdout).strip()[-8_192:]
        raise DecoderBuildError(f"Decoder command failed: {detail}")
    return completed


def _decoder_source(source: Path) -> Path:
    candidate = source / "sources" / "Android" / "android-communications" / "library" / "src" / "main" / "java"
    if not (candidate / "com/polar/androidcommunications/api/ble/model/offlinerecording/OfflineRecordingData.kt").is_file():
        raise DecoderBuildError("Active SDK revision does not contain the required Android communications source.")
    return candidate


def _java_environment(toolchain_root: Path) -> dict[str, str]:
    java_home = toolchain_root / "tools" / "jdk-21.0.12+8"
    if not (java_home / "bin" / "java").is_file():
        raise DecoderBuildError("Pinned JDK is missing after decoder setup.")
    environment = os.environ.copy()
    environment["JAVA_HOME"] = str(java_home)
    environment["PATH"] = f"{java_home / 'bin'}:{environment.get('PATH', '')}"
    return environment


def _verify_distribution(executable: Path, toolchain_root: Path) -> None:
    for command in ([str(executable), "version"], [str(executable), "self-test"]):
        completed = _run(list(command), timeout=30, environment=_java_environment(toolchain_root))
        try:
            status = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise DecoderBuildError("Decoder verification returned malformed JSON.") from exc
        if status.get("status") != "ok" or status.get("protocol_version") != 1:
            raise DecoderBuildError("Decoder verification did not confirm protocol v1.")


def build_decoder(
    *,
    commit: str | None = None,
    cache: SdkCache | None = None,
    activate: bool = True,
    offline: bool = False,
) -> DecoderBuildResult:
    cache = cache or SdkCache.default()
    if commit is None:
        commit, source = active_sdk_source(cache=cache)
    else:
        source = cache.sdk_path(commit) / "source"
        try:
            provenance = json.loads((cache.sdk_path(commit) / "download-manifest.json").read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise DecoderBuildError(f"SDK revision {commit} is not staged in the local cache.") from exc
        if provenance.get("resolved_commit") != commit or not source.is_dir():
            raise DecoderBuildError(f"SDK revision {commit} is not staged in the local cache.")
    if commit != SUPPORTED_SDK_COMMIT:
        raise DecoderBuildError(
            f"REC decoding currently supports only the pinned SDK revision {SUPPORTED_SDK_COMMIT}."
        )
    build_root = cache.decoder_build_path(commit)
    repo_root = Path(__file__).parents[3]
    setup_script, build_script = repo_root / "scripts" / "setup_rec_jvm_spike.sh", repo_root / "scripts" / "build_rec_jvm_decoder.sh"
    setup_command = [str(setup_script), "--root", str(build_root)]
    if offline:
        if not (build_root / "tools" / "jdk-21.0.12+8" / "bin" / "java").is_file():
            raise DecoderBuildError("Offline decoder build needs a pre-provisioned local toolchain.")
    else:
        _run(setup_command, timeout=900)
    _run([str(build_script), "--root", str(build_root), "--sdk-source", str(_decoder_source(source))], timeout=900)
    distribution = build_root / "decoder-dist"
    executable = distribution / "bin" / "polar-rec-decoder"
    if not executable.is_file() or executable.is_symlink():
        raise DecoderBuildError("Build did not produce the expected decoder executable.")
    _verify_distribution(executable, build_root)
    cache.decoder_root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=f".{commit[:12]}-", dir=cache.decoder_root) as temporary:
        staged = Path(temporary) / "decoder"
        shutil.copytree(distribution, staged)
        staged_executable = staged / "bin" / "polar-rec-decoder"
        manifest = {
            "manifest_version": 1, "decoder_protocol_version": 1, "sdk_commit": commit,
            "polar_ble_tools_version": __version__, "build_mode": "jvm",
            "build_timestamp_utc": datetime.now(UTC).isoformat(), "platform": platform.system().lower(),
            "architecture": platform.machine().lower(), "java_version": "21.0.12+8", "gradle_version": "9.4.1",
            "adapter_source_sha256": _adapter_digest(), "executable_relative_path": "bin/polar-rec-decoder",
            "executable_sha256": _digest(staged_executable), "verification_level": "handshake", "verified": True,
        }
        _write_json(staged / "manifest.json", manifest)
        target = cache.decoder_path(commit)
        if target.exists():
            shutil.rmtree(target)
        staged.replace(target)
    if activate:
        activate_decoder(commit, cache=cache)
    return DecoderBuildResult(commit, cache.decoder_path(commit), activate)


def activate_decoder(commit: str, *, cache: SdkCache | None = None) -> None:
    cache = cache or SdkCache.default()
    manifest = cache.decoder_path(commit) / "manifest.json"
    if not manifest.is_file():
        raise DecoderBuildError(f"Decoder {commit} is not built.")
    _write_json(cache.active_decoder_manifest_path, {"sdk_commit": commit})
    status = decoder_status(cache=cache)
    if not status.available:
        raise DecoderVerificationError(status.reason or "Activated decoder is not valid.")


def verify_decoder(*, cache: SdkCache | None = None) -> bool:
    cache = cache or SdkCache.default()
    status = decoder_status(cache=cache)
    if not status.available:
        raise DecoderManifestError(status.reason or "No verified decoder is active.")
    return True


def remove_decoder(commit: str, *, cache: SdkCache | None = None) -> bool:
    cache = cache or SdkCache.default()
    target = cache.decoder_path(commit)
    if not target.is_dir():
        return False
    active = cache.active_decoder_manifest_path
    if active.is_file():
        try:
            is_active = json.loads(active.read_text(encoding="utf-8")).get("sdk_commit") == commit
        except json.JSONDecodeError:
            is_active = False
        if is_active:
            active.unlink()
    shutil.rmtree(target)
    return True
