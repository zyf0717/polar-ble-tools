"""Build and activate the optional, locally compiled REC decoder sidecar."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import tarfile
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path, PurePosixPath
from tempfile import NamedTemporaryFile, TemporaryDirectory
from uuid import uuid4

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


_JDK_VERSION = "21.0.12+8"
_GRADLE_VERSION = "9.4.1"
_JDK_ARCHIVE = "OpenJDK21U-jdk_x64_linux_hotspot_21.0.12_8.tar.gz"
_GRADLE_ARCHIVE = f"gradle-{_GRADLE_VERSION}-bin.zip"
_JDK_URL = (
    "https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.12%2B8/"
    f"{_JDK_ARCHIVE}"
)
_GRADLE_URL = f"https://services.gradle.org/distributions/{_GRADLE_ARCHIVE}"
_JDK_SHA256 = "e4446ff06a276155697597cc0f1b15da004ff083f4964a35271ecee567177370"
_GRADLE_SHA256 = "2ab2958f2a1e51120c326cad6f385153bb11ee93b3c216c5fccebfdfbb7ec6cb"


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


def _restore_file(path: Path, payload: bytes | None) -> None:
    if payload is None:
        path.unlink(missing_ok=True)
        return
    with NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        temporary.write(payload)
        temporary_path = Path(temporary.name)
    temporary_path.replace(path)


def _promote_decoder_directory(staged: Path, target: Path) -> Path | None:
    """Replace a decoder entry while retaining the old entry for rollback."""
    backup: Path | None = None
    if target.exists():
        if not target.is_dir() or target.is_symlink():
            raise DecoderBuildError(f"Decoder target is not a regular directory: {target}")
        backup = target.with_name(f".{target.name}.previous-{uuid4().hex}")
        target.replace(backup)
    try:
        staged.replace(target)
    except BaseException:
        if backup is not None and backup.exists():
            backup.replace(target)
        raise
    return backup


def _restore_decoder_directory(target: Path, backup: Path | None) -> None:
    if backup is None:
        shutil.rmtree(target, ignore_errors=True)
    elif backup.exists():
        if target.exists():
            shutil.rmtree(target)
        backup.replace(target)


def _discard_decoder_backup(backup: Path | None) -> None:
    if backup is not None and backup.exists():
        shutil.rmtree(backup)


def _adapter_digest() -> str:
    hasher = hashlib.sha256()
    template = files("polar_ble_tools.sdk_tools").joinpath("decoder_project")
    for name in ("DecoderMain.kt", "build.gradle.kts", "settings.gradle.kts"):
        path = template.joinpath(name)
        if path.is_file():
            hasher.update(name.encode("utf-8"))
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
    java_home = toolchain_root / "tools" / f"jdk-{_JDK_VERSION}"
    if not (java_home / "bin" / "java").is_file():
        raise DecoderBuildError("Pinned JDK is missing after decoder setup.")
    environment = os.environ.copy()
    environment["JAVA_HOME"] = str(java_home)
    environment["PATH"] = f"{java_home / 'bin'}:{environment.get('PATH', '')}"
    return environment


def _download(url: str, destination: Path, expected_digest: str) -> None:
    if destination.is_file() and _digest(destination) == expected_digest:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=destination.parent, delete=False) as temporary:
        temporary_path = Path(temporary.name)
    try:
        with urllib.request.urlopen(url, timeout=60) as response, temporary_path.open("wb") as output:
            shutil.copyfileobj(response, output)
        if _digest(temporary_path) != expected_digest:
            raise DecoderBuildError(f"Checksum mismatch while downloading {destination.name}.")
        temporary_path.replace(destination)
    except OSError as exc:
        raise DecoderBuildError(f"Could not download {destination.name}: {exc}") from exc
    finally:
        temporary_path.unlink(missing_ok=True)


def _provision_toolchain(root: Path, *, offline: bool) -> None:
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        raise DecoderBuildError("REC decoder builds currently require Linux x86_64.")
    tools, downloads = root / "tools", root / "downloads"
    java, gradle = tools / f"jdk-{_JDK_VERSION}" / "bin" / "java", tools / f"gradle-{_GRADLE_VERSION}" / "bin" / "gradle"
    if java.is_file() and gradle.is_file():
        return
    if offline:
        raise DecoderBuildError("Offline decoder build needs a pre-provisioned local toolchain.")
    jdk_archive, gradle_archive = downloads / _JDK_ARCHIVE, downloads / _GRADLE_ARCHIVE
    _download(_JDK_URL, jdk_archive, _JDK_SHA256)
    _download(_GRADLE_URL, gradle_archive, _GRADLE_SHA256)
    tools.mkdir(parents=True, exist_ok=True)
    if not java.is_file():
        with TemporaryDirectory(prefix=".jdk-", dir=tools) as temporary:
            staged = Path(temporary) / "jdk"
            staged.mkdir()
            with tarfile.open(jdk_archive, "r:gz") as archive:
                for member in archive.getmembers():
                    parts = member.name.split("/")[1:]
                    if member.issym() or member.islnk() or ".." in parts:
                        raise DecoderBuildError("JDK archive contains an unsafe path.")
                    member.name = "/".join(parts)
                    if member.name:
                        archive.extract(member, staged)
            staged.replace(java.parent.parent)
    if not gradle.is_file():
        with TemporaryDirectory(prefix=".gradle-", dir=tools) as temporary:
            with zipfile.ZipFile(gradle_archive) as archive:
                for member in archive.infolist():
                    path = PurePosixPath(member.filename)
                    if path.is_absolute() or ".." in path.parts or (member.external_attr >> 16) & 0o170000 == 0o120000:
                        raise DecoderBuildError("Gradle archive contains an unsafe path.")
                    archive.extract(member, temporary)
            (Path(temporary) / f"gradle-{_GRADLE_VERSION}").replace(gradle.parent.parent)


def _write_workspace(workspace: Path) -> None:
    if workspace.exists():
        shutil.rmtree(workspace)
    source = workspace / "src" / "main" / "kotlin"
    source.mkdir(parents=True)
    template = files("polar_ble_tools.sdk_tools").joinpath("decoder_project")
    for name, destination in (
        ("settings.gradle.kts", workspace / "settings.gradle.kts"),
        ("build.gradle.kts", workspace / "build.gradle.kts"),
        ("DecoderMain.kt", source / "DecoderMain.kt"),
    ):
        destination.write_bytes(template.joinpath(name).read_bytes())


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
    _provision_toolchain(build_root, offline=offline)
    workspace = build_root / "workspace"
    _write_workspace(workspace)
    gradle = build_root / "tools" / f"gradle-{_GRADLE_VERSION}" / "bin" / "gradle"
    command = [
        str(gradle), "--no-daemon", "--project-dir", str(workspace),
        f"-PpolarSdkSource={_decoder_source(source)}", "installDist",
    ]
    if offline:
        command.insert(1, "--offline")
    environment = _java_environment(build_root)
    environment["GRADLE_USER_HOME"] = str(build_root / "gradle-user-home")
    _run(command, timeout=900, environment=environment)
    distribution = workspace / "build" / "install" / "polar-rec-decoder"
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
        backup = _promote_decoder_directory(staged, target)
        try:
            if activate:
                activate_decoder(commit, cache=cache)
        except BaseException:
            _restore_decoder_directory(target, backup)
            raise
        else:
            _discard_decoder_backup(backup)
    return DecoderBuildResult(commit, cache.decoder_path(commit), activate)


def activate_decoder(commit: str, *, cache: SdkCache | None = None) -> None:
    cache = cache or SdkCache.default()
    manifest = cache.decoder_path(commit) / "manifest.json"
    if not manifest.is_file():
        raise DecoderBuildError(f"Decoder {commit} is not built.")
    active_manifest = cache.active_decoder_manifest_path
    previous_payload = active_manifest.read_bytes() if active_manifest.exists() else None
    _write_json(active_manifest, {"sdk_commit": commit})
    status = decoder_status(cache=cache)
    if not status.available:
        _restore_file(active_manifest, previous_payload)
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
