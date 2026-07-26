"""Build and activate the optional, locally compiled REC decoder sidecar."""

from __future__ import annotations

import hashlib
import json
import os
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
from polar_ble_tools.rec import (
    DecoderManifestError,
    DecoderVerificationError,
    verify_active_decoder,
)
from polar_ble_tools.schemas.cache import SdkCache
from polar_ble_tools.sdk_tools.decoder.toolchain import (
    GRADLE_ARCHIVE,
    GRADLE_SHA256,
    GRADLE_URL,
    GRADLE_VERSION,
    JDK_ARCHIVE,
    JDK_SHA256,
    JDK_URL,
    JDK_VERSION,
    java_environment,
    normalized_architecture,
    normalized_platform,
)
from polar_ble_tools.sdk_tools.downloader import SUPPORTED_SDK_COMMIT, active_sdk_source
from polar_ble_tools.sdk_tools.revisions import require_full_commit, require_within


class DecoderBuildError(RuntimeError):
    """The local decoder could not be built or verified."""


@dataclass(frozen=True)
class DecoderBuildResult:
    sdk_commit: str
    decoder_path: Path
    activated: bool


_RUNTIME_LAUNCHERS = frozenset({"bin/polar-rec-decoder", "bin/polar-rec-decoder.bat"})


def _digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as current:
        for block in iter(lambda: current.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def _write_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary.write(json.dumps(value, sort_keys=True, indent=2) + "\n")
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


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
    require_within(staged, target.parent)
    require_within(target, target.parent)
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
    for name in ("DecoderMain.kt", "build.gradle.kts", "settings.gradle.kts", "gradle.lockfile"):
        path = template.joinpath(name)
        if path.is_file():
            hasher.update(name.encode("utf-8"))
            hasher.update(b"\0")
            hasher.update(path.read_bytes())
    return hasher.hexdigest()


def _runtime_file_digests(root: Path) -> dict[str, str]:
    """Return the complete, allowlisted runtime file set for a distribution."""
    files: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_dir():
            continue
        if path.is_symlink() or not path.is_file():
            raise DecoderBuildError(f"Decoder distribution has an unsafe entry: {path}")
        relative = path.relative_to(root).as_posix()
        allowed = relative in _RUNTIME_LAUNCHERS or (
            relative.startswith("lib/") and "/" not in relative[4:] and relative.endswith(".jar")
        )
        if not allowed:
            raise DecoderBuildError(f"Decoder distribution has an unexpected file: {relative}")
        files[relative] = _digest(path)
    if "bin/polar-rec-decoder" not in files or not any(path.startswith("lib/") for path in files):
        raise DecoderBuildError(
            "Decoder distribution is missing its launcher or runtime libraries."
        )
    return files


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
    candidate = (
        source
        / "sources"
        / "Android"
        / "android-communications"
        / "library"
        / "src"
        / "main"
        / "java"
    )
    if not (
        candidate
        / "com/polar/androidcommunications/api/ble/model/offlinerecording/OfflineRecordingData.kt"
    ).is_file():
        raise DecoderBuildError(
            "Active SDK revision does not contain the required Android communications source."
        )
    return candidate


def _java_environment(cache: SdkCache) -> dict[str, str]:
    try:
        return java_environment(
            cache.rec_jvm_java_home(normalized_platform(), normalized_architecture(), JDK_VERSION)
        )
    except RuntimeError as exc:
        raise DecoderBuildError(str(exc)) from exc


def _download(url: str, destination: Path, expected_digest: str) -> None:
    if destination.is_file() and _digest(destination) == expected_digest:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=destination.parent, delete=False) as temporary:
        temporary_path = Path(temporary.name)
    try:
        with (
            urllib.request.urlopen(url, timeout=60) as response,
            temporary_path.open("wb") as output,
        ):
            shutil.copyfileobj(response, output)
        if _digest(temporary_path) != expected_digest:
            raise DecoderBuildError(f"Checksum mismatch while downloading {destination.name}.")
        temporary_path.replace(destination)
    except OSError as exc:
        raise DecoderBuildError(f"Could not download {destination.name}: {exc}") from exc
    finally:
        temporary_path.unlink(missing_ok=True)


def _provision_toolchain(cache: SdkCache, build_root: Path, *, offline: bool) -> None:
    if normalized_platform() != "linux" or normalized_architecture() != "x86_64":
        raise DecoderBuildError("REC decoder builds currently require Linux x86_64.")
    tools, downloads = build_root / "tools", build_root / "downloads"
    java_home = cache.rec_jvm_java_home("linux", "x86_64", JDK_VERSION)
    java, gradle = (
        java_home / "bin" / "java",
        tools / f"gradle-{GRADLE_VERSION}" / "bin" / "gradle",
    )
    if java.is_file() and gradle.is_file():
        return
    if offline:
        raise DecoderBuildError("Offline decoder build needs a pre-provisioned local toolchain.")
    jdk_archive, gradle_archive = downloads / JDK_ARCHIVE, downloads / GRADLE_ARCHIVE
    _download(JDK_URL, jdk_archive, JDK_SHA256)
    _download(GRADLE_URL, gradle_archive, GRADLE_SHA256)
    tools.mkdir(parents=True, exist_ok=True)
    if not java.is_file():
        java_home.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix=".jdk-", dir=java_home.parent) as temporary:
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
            staged.replace(java_home)
    if not gradle.is_file():
        with TemporaryDirectory(prefix=".gradle-", dir=tools) as temporary:
            with zipfile.ZipFile(gradle_archive) as archive:
                for member in archive.infolist():
                    path = PurePosixPath(member.filename)
                    if (
                        path.is_absolute()
                        or ".." in path.parts
                        or (member.external_attr >> 16) & 0o170000 == 0o120000
                    ):
                        raise DecoderBuildError("Gradle archive contains an unsafe path.")
                    archive.extract(member, temporary)
            (Path(temporary) / f"gradle-{GRADLE_VERSION}").replace(gradle.parent.parent)


def _write_workspace(workspace: Path, *, commit: str) -> None:
    if workspace.exists():
        shutil.rmtree(workspace)
    source = workspace / "src" / "main" / "kotlin"
    source.mkdir(parents=True)
    template = files("polar_ble_tools.sdk_tools").joinpath("decoder_project")
    for name, destination in (
        ("settings.gradle.kts", workspace / "settings.gradle.kts"),
        ("build.gradle.kts", workspace / "build.gradle.kts"),
        ("gradle.lockfile", workspace / "gradle.lockfile"),
        ("DecoderMain.kt", source / "DecoderMain.kt"),
    ):
        template_path = template.joinpath(name)
        if template_path.is_file():
            destination.write_bytes(template_path.read_bytes())
    (source / "BuildInfo.kt").write_text(
        "object BuildInfo {\n"
        f'    const val DECODER_VERSION = "{__version__}"\n'
        f'    const val SDK_COMMIT = "{commit}"\n'
        "    const val PROTOCOL_VERSION = 1\n"
        "}\n",
        encoding="utf-8",
    )


def _verify_distribution(executable: Path, cache: SdkCache, *, commit: str) -> None:
    for command in ([str(executable), "version"], [str(executable), "self-test"]):
        completed = _run(list(command), timeout=30, environment=_java_environment(cache))
        try:
            status = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise DecoderBuildError("Decoder verification returned malformed JSON.") from exc
        if (
            status.get("status") != "ok"
            or status.get("protocol_version") != 1
            or status.get("sdk_commit") != commit
            or status.get("decoder_version") != __version__
        ):
            raise DecoderBuildError(
                "Decoder verification did not confirm the expected protocol and provenance."
            )


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
        try:
            commit = require_full_commit(commit)
        except ValueError as exc:
            raise DecoderBuildError(str(exc)) from exc
        source = cache.sdk_path(commit) / "source"
        try:
            provenance = json.loads((cache.sdk_path(commit) / "download-manifest.json").read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise DecoderBuildError(
                f"SDK revision {commit} is not staged in the local cache."
            ) from exc
        if provenance.get("resolved_commit") != commit or not source.is_dir():
            raise DecoderBuildError(f"SDK revision {commit} is not staged in the local cache.")
    try:
        commit = require_full_commit(commit)
    except ValueError as exc:
        raise DecoderBuildError(str(exc)) from exc
    if commit != SUPPORTED_SDK_COMMIT:
        raise DecoderBuildError(
            f"REC decoding currently supports only the pinned SDK revision {SUPPORTED_SDK_COMMIT}."
        )
    build_root = cache.decoder_build_path(commit)
    _provision_toolchain(cache, build_root, offline=offline)
    workspace = build_root / "workspace"
    _write_workspace(workspace, commit=commit)
    gradle = build_root / "tools" / f"gradle-{GRADLE_VERSION}" / "bin" / "gradle"
    command = [
        str(gradle),
        "--no-daemon",
        "--project-dir",
        str(workspace),
        f"-PpolarSdkSource={_decoder_source(source)}",
        "installDist",
    ]
    if offline:
        command.insert(1, "--offline")
    environment = _java_environment(cache)
    environment["GRADLE_USER_HOME"] = str(build_root / "gradle-user-home")
    _run(command, timeout=900, environment=environment)
    distribution = workspace / "build" / "install" / "polar-rec-decoder"
    executable = distribution / "bin" / "polar-rec-decoder"
    if not executable.is_file() or executable.is_symlink():
        raise DecoderBuildError("Build did not produce the expected decoder executable.")
    _verify_distribution(executable, cache, commit=commit)
    cache.decoder_root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=f".{commit[:12]}-", dir=cache.decoder_root) as temporary:
        staged = Path(temporary) / "decoder"
        shutil.copytree(distribution, staged)
        staged_executable = staged / "bin" / "polar-rec-decoder"
        runtime_files = _runtime_file_digests(staged)
        manifest = {
            "manifest_version": 1,
            "decoder_protocol_version": 1,
            "sdk_commit": commit,
            "decoder_version": __version__,
            "polar_ble_tools_version": __version__,
            "build_mode": "jvm",
            "build_timestamp_utc": datetime.now(UTC).isoformat(),
            "platform": normalized_platform(),
            "architecture": normalized_architecture(),
            "java_version": JDK_VERSION,
            "gradle_version": GRADLE_VERSION,
            "adapter_source_sha256": _adapter_digest(),
            "executable_relative_path": "bin/polar-rec-decoder",
            "executable_sha256": _digest(staged_executable),
            "verification_level": "handshake",
            "verified": True,
            "runtime_files": runtime_files,
            "runtime": {
                "kind": "pinned-jvm",
                "platform": normalized_platform(),
                "architecture": normalized_architecture(),
                "java_version": JDK_VERSION,
                "java_relative_cache_path": str(
                    cache.rec_jvm_java_home(
                        normalized_platform(), normalized_architecture(), JDK_VERSION
                    ).relative_to(cache.root)
                ),
                "java_executable_sha256": _digest(
                    cache.rec_jvm_java_home(
                        normalized_platform(), normalized_architecture(), JDK_VERSION
                    )
                    / "bin"
                    / "java"
                ),
            },
        }
        _write_json(staged / "manifest.json", manifest)
        try:
            target = require_within(cache.decoder_path(commit), cache.decoder_root)
        except ValueError as exc:
            raise DecoderBuildError(str(exc)) from exc
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
    try:
        commit = require_full_commit(commit)
        manifest = require_within(cache.decoder_path(commit), cache.decoder_root) / "manifest.json"
    except ValueError as exc:
        raise DecoderBuildError(str(exc)) from exc
    if not manifest.is_file():
        raise DecoderBuildError(f"Decoder {commit} is not built.")
    active_manifest = cache.active_decoder_manifest_path
    previous_payload = active_manifest.read_bytes() if active_manifest.exists() else None
    _write_json(active_manifest, {"sdk_commit": commit})
    try:
        verify_active_decoder(cache=cache)
    except (DecoderManifestError, DecoderVerificationError) as exc:
        _restore_file(active_manifest, previous_payload)
        raise DecoderVerificationError(str(exc)) from exc


def verify_decoder(*, cache: SdkCache | None = None) -> bool:
    cache = cache or SdkCache.default()
    return verify_active_decoder(cache=cache)


def remove_decoder(commit: str, *, cache: SdkCache | None = None) -> bool:
    cache = cache or SdkCache.default()
    try:
        commit = require_full_commit(commit)
        target = require_within(cache.decoder_path(commit), cache.decoder_root)
        build_target = require_within(cache.decoder_build_path(commit), cache.decoder_build_root)
    except ValueError as exc:
        raise DecoderBuildError(str(exc)) from exc
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
    if build_target.exists():
        shutil.rmtree(build_target)
    return True
