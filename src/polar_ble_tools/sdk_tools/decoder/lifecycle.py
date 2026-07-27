"""Build and activate the optional, locally compiled REC decoder sidecar."""

from __future__ import annotations

import hashlib
import json
import os
import posixpath
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
from polar_ble_tools.sdk_tools.decoder.errors import (
    LicenseAcceptanceMismatchError,
    LicenseAcceptanceRequiredError,
    LicenseNoticeMissingError,
    SdkLifecycleError,
)
from polar_ble_tools.sdk_tools.decoder.toolchain import (
    ToolchainDescriptor,
    java_environment,
    java_executable,
    java_home,
    toolchain_descriptor,
    toolchain_descriptor_digest,
)
from polar_ble_tools.sdk_tools.downloader import (
    MANIFEST_FILE,
    SDK_LICENSE_FILE,
    SDK_NOTICE_FILES,
    SUPPORTED_SDK_COMMIT,
    active_sdk_source,
    source_content_sha256,
)
from polar_ble_tools.sdk_tools.revisions import require_full_commit, require_within


class DecoderBuildError(RuntimeError):
    """The local decoder could not be built or verified."""


@dataclass(frozen=True)
class DecoderBuildResult:
    sdk_commit: str
    decoder_path: Path
    activated: bool


_RUNTIME_LAUNCHERS = frozenset({"bin/polar-rec-decoder", "bin/polar-rec-decoder.bat"})
_LICENSE_RELATIVE_PATH = f"licenses/{SDK_LICENSE_FILE}"
_NOTICE_RELATIVE_PATHS = {name: f"notices/{name}" for name in SDK_NOTICE_FILES}
_TOOLCHAIN_MANIFEST = ".polar-rec-toolchain.json"


@dataclass(frozen=True)
class _SdkMaterial:
    kind: str
    source_path: Path
    cache_relative_path: str
    sha256: str
    source_identity: str


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


def _sdk_material(cache: SdkCache, commit: str, source: Path) -> tuple[_SdkMaterial, ...]:
    sdk_root = cache.sdk_path(commit)
    expected_source = sdk_root / "source"
    if source.resolve() != expected_source.resolve():
        raise LicenseAcceptanceMismatchError(
            "Decoder build source does not match the staged SDK cache entry."
        )
    try:
        manifest = json.loads((sdk_root / MANIFEST_FILE).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LicenseAcceptanceRequiredError(
            "SDK licence acceptance is missing; rerun: polar-ble sdk install --accept-license"
        ) from exc
    acceptance = manifest.get("license_acceptance")
    content_digest = manifest.get("source_content_sha256")
    if (
        manifest.get("format_version") != 5
        or manifest.get("resolved_commit") != commit
        or not isinstance(content_digest, str)
        or len(content_digest) != 64
        or not isinstance(acceptance, dict)
        or acceptance.get("method") != "cli_flag"
        or acceptance.get("resolved_commit") != commit
        or acceptance.get("license_filename") != SDK_LICENSE_FILE
        or acceptance.get("source_identity") != f"sha256:{content_digest}"
        or not isinstance(acceptance.get("accepted_at"), str)
        or not acceptance["accepted_at"]
        or not isinstance(acceptance.get("license_sha256"), str)
    ):
        raise LicenseAcceptanceRequiredError(
            "SDK licence acceptance is not content-bound; rerun: "
            "polar-ble sdk install --accept-license"
        )
    if source_content_sha256(source) != content_digest:
        raise LicenseAcceptanceMismatchError(
            "Staged SDK content changed after licence acceptance; reinstall it explicitly."
        )
    license_digest = str(acceptance["license_sha256"])
    source_license = source / SDK_LICENSE_FILE
    cached_license = sdk_root / SDK_LICENSE_FILE
    for path in (source_license, cached_license):
        if not path.is_file() or path.is_symlink():
            raise LicenseNoticeMissingError(f"Required local SDK material is missing: {path.name}")
        if _digest(path) != license_digest:
            raise LicenseAcceptanceMismatchError(
                "Staged SDK licence differs from its accepted digest."
            )
    identity = str(acceptance["source_identity"])
    materials = [
        _SdkMaterial(
            "license",
            source_license,
            _LICENSE_RELATIVE_PATH,
            license_digest,
            identity,
        )
    ]
    for name, relative in _NOTICE_RELATIVE_PATHS.items():
        notice = source / name
        if not notice.is_file() or notice.is_symlink():
            raise LicenseNoticeMissingError(f"Required local SDK notice is missing: {name}")
        materials.append(_SdkMaterial("notice", notice, relative, _digest(notice), identity))
    return tuple(materials)


def _copy_sdk_material(staged: Path, materials: tuple[_SdkMaterial, ...]) -> None:
    for material in materials:
        destination = staged / material.cache_relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(material.source_path, destination)


def _java_environment(cache: SdkCache, descriptor: ToolchainDescriptor) -> dict[str, str]:
    try:
        return java_environment(
            java_home(cache, descriptor),
            java_relative_path=descriptor.java_relative_path,
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


def _safe_jdk_archive_member(member: tarfile.TarInfo, archive_root: str) -> bool:
    """Validate and strip the single top-level JDK archive directory."""
    name = PurePosixPath(member.name)
    if (
        name.is_absolute()
        or not name.parts
        or name.parts[0] != archive_root
        or ".." in name.parts
        or member.isdev()
    ):
        raise DecoderBuildError("JDK archive contains an unsafe path.")
    relative = PurePosixPath(*name.parts[1:])
    if not relative.parts:
        return False
    if member.issym() or member.islnk():
        link = PurePosixPath(member.linkname)
        target = PurePosixPath(posixpath.normpath(str(name.parent / link)))
        if (
            link.is_absolute()
            or not target.parts
            or target.parts[0] != archive_root
            or ".." in target.parts
        ):
            raise DecoderBuildError("JDK archive contains an unsafe link.")
    member.name = relative.as_posix()
    return True


def _replace_incomplete_directory(staged: Path, target: Path, *, description: str) -> None:
    """Promote a staged directory over an interrupted regular-directory install."""
    if target.exists() or target.is_symlink():
        if not target.is_dir() or target.is_symlink():
            raise DecoderBuildError(f"{description} target is not a regular directory: {target}")
        shutil.rmtree(target)
    staged.replace(target)


def _tool_entry_verified(
    root: Path,
    executable: Path,
    descriptor: ToolchainDescriptor,
    *,
    kind: str,
    archive_sha256: str,
) -> bool:
    manifest_path = root / _TOOLCHAIN_MANIFEST
    if (
        not root.is_dir()
        or root.is_symlink()
        or not executable.is_file()
        or executable.is_symlink()
        or not os.access(executable, os.X_OK)
        or not manifest_path.is_file()
        or manifest_path.is_symlink()
    ):
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return manifest == {
        "archive_sha256": archive_sha256,
        "executable_relative_path": executable.relative_to(root).as_posix(),
        "executable_sha256": _digest(executable),
        "kind": kind,
        "toolchain_descriptor_sha256": toolchain_descriptor_digest(descriptor),
    }


def _write_tool_entry_manifest(
    root: Path,
    executable: Path,
    descriptor: ToolchainDescriptor,
    *,
    kind: str,
    archive_sha256: str,
) -> None:
    if not executable.is_file() or executable.is_symlink() or not os.access(executable, os.X_OK):
        raise DecoderBuildError(f"Extracted {kind} executable is missing or unsafe.")
    _write_json(
        root / _TOOLCHAIN_MANIFEST,
        {
            "archive_sha256": archive_sha256,
            "executable_relative_path": executable.relative_to(root).as_posix(),
            "executable_sha256": _digest(executable),
            "kind": kind,
            "toolchain_descriptor_sha256": toolchain_descriptor_digest(descriptor),
        },
    )


def _provision_toolchain(
    cache: SdkCache,
    build_root: Path,
    descriptor: ToolchainDescriptor,
    *,
    offline: bool,
) -> None:
    tools, downloads = build_root / "tools", build_root / "downloads"
    jdk_home = java_home(cache, descriptor)
    java, gradle = (
        java_executable(cache, descriptor),
        tools / f"gradle-{descriptor.gradle_version}" / "bin" / "gradle",
    )
    jdk_ready = _tool_entry_verified(
        jdk_home,
        java,
        descriptor,
        kind="jdk",
        archive_sha256=descriptor.jdk_sha256,
    )
    gradle_root = gradle.parent.parent
    gradle_ready = _tool_entry_verified(
        gradle_root,
        gradle,
        descriptor,
        kind="gradle",
        archive_sha256=descriptor.gradle_sha256,
    )
    if jdk_ready and gradle_ready:
        return
    if offline:
        raise DecoderBuildError(
            "Offline decoder build needs a complete descriptor-verified local toolchain."
        )
    jdk_archive = downloads / descriptor.jdk_archive_name
    gradle_archive = downloads / descriptor.gradle_archive_name
    _download(descriptor.jdk_url, jdk_archive, descriptor.jdk_sha256)
    _download(descriptor.gradle_url, gradle_archive, descriptor.gradle_sha256)
    tools.mkdir(parents=True, exist_ok=True)
    if not jdk_ready:
        jdk_home.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix=".jdk-", dir=jdk_home.parent) as temporary:
            staged = Path(temporary) / "jdk"
            staged.mkdir()
            with tarfile.open(jdk_archive, "r:gz") as archive:
                for member in archive.getmembers():
                    if _safe_jdk_archive_member(member, descriptor.jdk_archive_root):
                        archive.extract(member, staged)
            _write_tool_entry_manifest(
                staged,
                staged / descriptor.java_relative_path,
                descriptor,
                kind="jdk",
                archive_sha256=descriptor.jdk_sha256,
            )
            _replace_incomplete_directory(staged, jdk_home, description="JDK")
    if not gradle_ready:
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
            staged_gradle = Path(temporary) / f"gradle-{descriptor.gradle_version}"
            _write_tool_entry_manifest(
                staged_gradle,
                staged_gradle / "bin" / "gradle",
                descriptor,
                kind="gradle",
                archive_sha256=descriptor.gradle_sha256,
            )
            _replace_incomplete_directory(
                staged_gradle,
                gradle_root,
                description="Gradle",
            )


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


def _verify_distribution(
    executable: Path,
    cache: SdkCache,
    descriptor: ToolchainDescriptor,
    *,
    commit: str,
) -> None:
    for command in ([str(executable), "version"], [str(executable), "self-test"]):
        completed = _run(
            list(command),
            timeout=30,
            environment=_java_environment(cache, descriptor),
        )
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
    materials = _sdk_material(cache, commit, source)
    try:
        descriptor = toolchain_descriptor()
    except RuntimeError as exc:
        raise DecoderBuildError(str(exc)) from exc
    build_root = cache.decoder_build_path(commit)
    _provision_toolchain(cache, build_root, descriptor, offline=offline)
    workspace = build_root / "workspace"
    _write_workspace(workspace, commit=commit)
    gradle = build_root / "tools" / f"gradle-{descriptor.gradle_version}" / "bin" / "gradle"
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
    environment = _java_environment(cache, descriptor)
    environment["GRADLE_USER_HOME"] = str(build_root / "gradle-user-home")
    _run(command, timeout=900, environment=environment)
    distribution = workspace / "build" / "install" / "polar-rec-decoder"
    executable = distribution / "bin" / "polar-rec-decoder"
    if not executable.is_file() or executable.is_symlink():
        raise DecoderBuildError("Build did not produce the expected decoder executable.")
    _verify_distribution(executable, cache, descriptor, commit=commit)
    cache.decoder_root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=f".{commit[:12]}-", dir=cache.decoder_root) as temporary:
        staged = Path(temporary) / "decoder"
        shutil.copytree(distribution, staged)
        _copy_sdk_material(staged, materials)
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
            "platform": descriptor.platform,
            "architecture": descriptor.architecture,
            "java_version": descriptor.jdk_version,
            "java_archive_sha256": descriptor.jdk_sha256,
            "gradle_version": descriptor.gradle_version,
            "gradle_archive_sha256": descriptor.gradle_sha256,
            "toolchain_descriptor_sha256": toolchain_descriptor_digest(descriptor),
            "adapter_source_sha256": _adapter_digest(),
            "executable_relative_path": "bin/polar-rec-decoder",
            "executable_sha256": _digest(staged_executable),
            "verification_level": "handshake",
            "verified": True,
            "runtime_files": runtime_files,
            "sdk_source_content_sha256": materials[0].source_identity.removeprefix("sha256:"),
            "license_material": [
                {
                    "kind": material.kind,
                    "cache_relative_path": material.cache_relative_path,
                    "sha256": material.sha256,
                    "source_identity": material.source_identity,
                }
                for material in materials
            ],
            "runtime": {
                "kind": "pinned-jvm",
                "platform": descriptor.platform,
                "architecture": descriptor.architecture,
                "java_version": descriptor.jdk_version,
                "java_relative_cache_path": str(
                    java_home(cache, descriptor).relative_to(cache.root)
                ),
                "java_relative_path": descriptor.java_relative_path,
                "java_executable_sha256": _digest(java_executable(cache, descriptor)),
                "toolchain_descriptor_sha256": toolchain_descriptor_digest(descriptor),
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
    except (DecoderManifestError, DecoderVerificationError, SdkLifecycleError) as exc:
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
    removed = False
    if target.is_dir() and not target.is_symlink():
        shutil.rmtree(target)
        removed = True
    active = cache.active_decoder_manifest_path
    if active.is_file():
        try:
            is_active = json.loads(active.read_text(encoding="utf-8")).get("sdk_commit") == commit
        except json.JSONDecodeError:
            is_active = False
        if is_active:
            active.unlink()
    if build_target.exists():
        if not build_target.is_dir() or build_target.is_symlink():
            raise DecoderBuildError(
                f"Decoder build workspace is not a regular directory: {build_target}"
            )
        shutil.rmtree(build_target)
        removed = True
    return removed
