from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from polar_ble_tools.schemas.cache import SdkCache

OFFICIAL_SDK_URL = "https://github.com/polarofficial/polar-ble-sdk.git"
# Release-owned compatibility contract. Override commits are recorded but are
# not covered by this package's schema or device compatibility evidence.
SUPPORTED_SDK_COMMIT = "ccff6812c40fff1753c72385387d1877ca9b27b4"
PINNED_SDK_COMMIT = SUPPORTED_SDK_COMMIT
MANIFEST_FILE = "download-manifest.json"
SDK_LICENSE_FILE = "Polar_SDK_License.txt"
_LEGACY_ACCEPTANCE_FIELDS = frozenset({"license_acceptance", "license_notice_present"})
_LEGACY_LICENSE_COPY = SDK_LICENSE_FILE
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


class SdkDownloadError(RuntimeError):
    """Raised when an SDK source cannot be staged locally."""


@dataclass(frozen=True)
class SdkInstallResult:
    requested_ref: str
    resolved_commit: str
    source_url: str
    source_path: Path
    manifest_path: Path
    reused: bool
    support_tier: str


@dataclass(frozen=True)
class SdkStatus:
    active_commit: str | None
    installed_commits: tuple[str, ...]


def _run_git(*args: str, cwd: Path | None = None) -> str:
    try:
        completed = subprocess.run(
            ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
        )
    except FileNotFoundError as exc:
        raise SdkDownloadError("git is required to download the Polar SDK.") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "unknown git failure").strip()
        raise SdkDownloadError(f"Git command failed: {' '.join(args)}: {detail}") from exc
    return completed.stdout.strip()


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _manifest_payload(
    *,
    source_type: str,
    requested_ref: str,
    resolved_commit: str,
    support_tier: str,
    source_content_sha256: str,
) -> dict[str, object]:
    return {
        "format_version": 4,
        "vendor": "polar",
        "source_type": source_type,
        "source_repository": OFFICIAL_SDK_URL if source_type == "official" else "user-supplied",
        "requested_ref": requested_ref,
        "resolved_commit": resolved_commit,
        "supported_commit": SUPPORTED_SDK_COMMIT,
        "support_tier": support_tier,
        "installed_at": datetime.now(UTC).isoformat(),
        "source_content_sha256": source_content_sha256,
    }


def source_content_sha256(source: Path) -> str:
    """Return a stable digest for an SDK source tree without cache artifacts."""
    digest = hashlib.sha256()
    for root, directories, files in os.walk(source):
        root_path = Path(root)
        retained_directories: list[str] = []
        for name in sorted(name for name in directories if name not in {".git", "__pycache__"}):
            if (root_path / name).is_symlink():
                raise SdkDownloadError("SDK source contains an unsafe symbolic link.")
            retained_directories.append(name)
        directories[:] = retained_directories
        for name in sorted(files):
            if name.endswith(".pyc"):
                continue
            path = root_path / name
            if path.is_symlink():
                raise SdkDownloadError("SDK source contains an unsafe symbolic link.")
            if not path.is_file():
                raise SdkDownloadError("SDK source contains an unsafe non-regular file.")
            relative = path.relative_to(source).as_posix()
            digest.update(relative.encode("utf-8"))
            digest.update(b"\0")
            with path.open("rb") as current:
                for block in iter(lambda: current.read(1024 * 1024), b""):
                    digest.update(block)
    return digest.hexdigest()


def _local_source_identity(source: Path) -> tuple[str, str]:
    """Return a stable cache revision and full content digest for a local source."""
    content_sha256 = source_content_sha256(source)
    # Cache paths and activation already use 40-hex revision identifiers. A
    # SHA-256 prefix gives local snapshots immutable addressing without
    # falsely claiming the user supplied a Git commit.
    return content_sha256[:40], content_sha256


def _existing_result(cache: SdkCache, commit: str) -> SdkInstallResult | None:
    root = cache.sdk_path(commit)
    source = root / "source"
    manifest = root / MANIFEST_FILE
    if not (source.is_dir() and manifest.is_file()):
        return None
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SdkDownloadError(f"Invalid SDK manifest at {manifest}.") from exc
    if payload.get("resolved_commit") != commit:
        raise SdkDownloadError(f"Existing SDK cache entry {root} is for a different SDK release.")
    tier = str(payload.get("support_tier", ""))
    if tier not in {"pinned", "override"}:
        tier = "pinned" if commit == SUPPORTED_SDK_COMMIT else "override"
    return SdkInstallResult(
        str(payload.get("requested_ref", commit)),
        commit,
        str(payload.get("source_repository", "unknown")),
        source,
        manifest,
        True,
        tier,
    )


def _stage_source(
    source: Path,
    *,
    source_type: str,
    requested_ref: str,
    resolved_commit: str,
    support_tier: str,
    cache: SdkCache,
    source_tree_sha256: str | None = None,
) -> SdkInstallResult:
    existing = _existing_result(cache, resolved_commit)
    if existing is not None:
        return existing
    content_sha256 = source_tree_sha256 or source_content_sha256(source)
    cache.sdk_root.mkdir(parents=True, exist_ok=True)
    destination = cache.sdk_path(resolved_commit)
    with TemporaryDirectory(prefix=f".{resolved_commit[:12]}-", dir=cache.sdk_root) as temporary:
        staged_root = Path(temporary) / "entry"
        staged_source = staged_root / "source"
        shutil.copytree(
            source, staged_source, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc")
        )
        manifest = staged_root / MANIFEST_FILE
        _atomic_write_json(
            manifest,
            _manifest_payload(
                source_type=source_type,
                requested_ref=requested_ref,
                resolved_commit=resolved_commit,
                support_tier=support_tier,
                source_content_sha256=content_sha256,
            ),
        )
        try:
            staged_root.replace(destination)
        except FileExistsError:
            existing = _existing_result(cache, resolved_commit)
            if existing is None:
                raise
            return existing
    return SdkInstallResult(
        requested_ref,
        resolved_commit,
        OFFICIAL_SDK_URL if source_type == "official" else "user-supplied",
        destination / "source",
        destination / MANIFEST_FILE,
        False,
        support_tier,
    )


def _activate(cache: SdkCache, commit: str) -> None:
    _atomic_write_json(cache.active_manifest_path, {"resolved_commit": commit})


def _discard_legacy_acceptance_state(cache: SdkCache, result: SdkInstallResult) -> None:
    """Remove package-created acceptance records after fresh explicit consent."""
    try:
        payload = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SdkDownloadError(f"Invalid SDK manifest at {result.manifest_path}.") from exc
    legacy_copies = (
        result.manifest_path.parent / _LEGACY_LICENSE_COPY,
        cache.generated_path(result.resolved_commit) / _LEGACY_LICENSE_COPY,
    )
    for path in legacy_copies:
        if path.exists() and not (path.is_file() or path.is_symlink()):
            raise SdkDownloadError(f"Legacy SDK acceptance artifact is not a file: {path}")
    for path in legacy_copies:
        if path.is_file() or path.is_symlink():
            path.unlink()
    if _LEGACY_ACCEPTANCE_FIELDS.intersection(payload):
        for field in _LEGACY_ACCEPTANCE_FIELDS:
            payload.pop(field, None)
        if payload.get("format_version") == 5:
            payload["format_version"] = 4
        _atomic_write_json(result.manifest_path, payload)


def install_sdk(
    *,
    ref: str | None = None,
    sdk_path: Path | None = None,
    cache: SdkCache | None = None,
    activate: bool = True,
) -> SdkInstallResult:
    """Stage the release pin by default or an explicitly requested override.

    Every call to this explicit installation API implies fresh acceptance of
    the SDK's licence terms. The CLI confirms this before every invocation,
    including cache reuse.
    """
    cache = cache or SdkCache.default()
    if sdk_path is not None:
        if ref is not None:
            raise SdkDownloadError("Use either an official --ref or --sdk-path, not both.")
        source = sdk_path.expanduser().resolve()
        if not source.is_dir():
            raise SdkDownloadError(f"SDK path does not exist: {source}")
        revision, content_sha256 = _local_source_identity(source)
        # A local path is intentionally an override. Its content-addressed cache
        # revision prevents a changed checkout from reusing an older cache.
        result = _stage_source(
            source,
            source_type="user_path",
            requested_ref=str(source),
            resolved_commit=revision,
            support_tier="override",
            source_tree_sha256=content_sha256,
            cache=cache,
        )
    else:
        requested_ref = ref or SUPPORTED_SDK_COMMIT
        with TemporaryDirectory(prefix="polar-ble-sdk-") as temporary:
            source = Path(temporary) / "source"
            _run_git("clone", "--no-checkout", "--filter=blob:none", OFFICIAL_SDK_URL, str(source))
            _run_git("checkout", "--detach", requested_ref, cwd=source)
            resolved_commit = _run_git("rev-parse", "--verify", "HEAD^{commit}", cwd=source).lower()
            if not _COMMIT_RE.fullmatch(resolved_commit):
                raise SdkDownloadError("SDK ref did not resolve to a full commit SHA.")
            result = _stage_source(
                source,
                source_type="official",
                requested_ref=requested_ref,
                resolved_commit=resolved_commit,
                support_tier="pinned" if resolved_commit == SUPPORTED_SDK_COMMIT else "override",
                cache=cache,
            )
    _discard_legacy_acceptance_state(cache, result)
    if activate:
        _activate(cache, result.resolved_commit)
    return result


def activate_sdk(commit: str, *, cache: SdkCache | None = None) -> None:
    cache = cache or SdkCache.default()
    if not _COMMIT_RE.fullmatch(commit) or _existing_result(cache, commit) is None:
        raise SdkDownloadError(f"SDK revision {commit} is not staged in the local cache.")
    _activate(cache, commit)


def sdk_status(*, cache: SdkCache | None = None) -> SdkStatus:
    cache = cache or SdkCache.default()
    installed = ()
    if cache.sdk_root.is_dir():
        installed = tuple(
            sorted(
                path.name
                for path in cache.sdk_root.iterdir()
                if path.is_dir()
                and _COMMIT_RE.fullmatch(path.name)
                and (path / MANIFEST_FILE).is_file()
            )
        )
    active_commit: str | None = None
    if cache.active_manifest_path.is_file():
        try:
            active_commit = json.loads(cache.active_manifest_path.read_text(encoding="utf-8")).get(
                "resolved_commit"
            )
        except json.JSONDecodeError:
            active_commit = None
        if active_commit not in installed:
            active_commit = None
    return SdkStatus(active_commit=active_commit, installed_commits=installed)


def active_sdk_source(*, cache: SdkCache | None = None) -> tuple[str, Path]:
    cache = cache or SdkCache.default()
    active_commit = sdk_status(cache=cache).active_commit
    if active_commit is None:
        raise SdkDownloadError("No active Polar SDK is installed. Run: polar-ble sdk install")
    source = cache.sdk_path(active_commit) / "source"
    if not source.is_dir():
        raise SdkDownloadError(f"Active Polar SDK source is missing: {source}")
    return active_commit, source


def remove_sdk(commit: str, *, cache: SdkCache | None = None) -> bool:
    if not _COMMIT_RE.fullmatch(commit):
        raise SdkDownloadError("SDK removal requires a full 40-character commit SHA.")
    from polar_ble_tools.schemas.runtime import schema_activation_manager

    cache = cache or SdkCache.default()
    schema_activation_manager(cache).ensure_removable(commit)
    sdk_target, generated_target = cache.sdk_path(commit), cache.generated_path(commit)
    if not sdk_target.is_dir() and not generated_target.is_dir():
        return False
    was_active = sdk_status(cache=cache).active_commit == commit
    for target in (sdk_target, generated_target):
        if target.is_dir():
            shutil.rmtree(target)
    if was_active:
        cache.active_manifest_path.unlink(missing_ok=True)
    return True


def remove_all_sdk_cache(*, cache: SdkCache | None = None) -> bool:
    from polar_ble_tools.schemas.runtime import schema_activation_manager

    cache = cache or SdkCache.default()
    schema_activation_manager(cache).ensure_removable(None)
    removed = False
    for target in (cache.sdk_root, cache.generated_root):
        if target.is_dir():
            shutil.rmtree(target)
            removed = True
    if cache.active_manifest_path.exists():
        cache.active_manifest_path.unlink()
        removed = True
    return removed
