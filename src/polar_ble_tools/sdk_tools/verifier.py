from __future__ import annotations

import hashlib
import importlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from tempfile import mkstemp

from polar_ble_tools.schemas.cache import SdkCache
from polar_ble_tools.schemas.requirements import requirements_for
from polar_ble_tools.sdk_tools.generator import GENERATED_MANIFEST
from polar_ble_tools.sdk_tools.requirement_scan import (
    SchemaRequirementDriftError,
    reconcile_schema_requirements,
)
from polar_ble_tools.sdk_tools.revisions import require_full_commit

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class SchemaVerificationError(RuntimeError):
    """Raised when local generated schemas are missing or invalid."""


@dataclass(frozen=True)
class SchemaStatus:
    active_commit: str | None
    installed_commits: tuple[str, ...]
    manifest_format: int | None
    source_independent: bool
    unavailable_reason: str | None = None


@dataclass(frozen=True)
class SchemaProvenance:
    resolved_commit: str
    manifest_format: int
    descriptor_sha256: str
    source_content_sha256: str | None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_manifest(root: Path, commit: str) -> dict[str, object]:
    manifest_path = root / GENERATED_MANIFEST
    if (
        root.is_symlink()
        or not root.is_dir()
        or manifest_path.is_symlink()
        or not manifest_path.is_file()
    ):
        raise SchemaVerificationError(
            "Generated schemas are not installed. Run: polar-ble sdk generate"
        )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SchemaVerificationError(
            f"Invalid generated schema manifest: {manifest_path}"
        ) from exc
    required = {
        "source_repository",
        "requested_ref",
        "resolved_commit",
        "descriptor_sha256",
        "required_features",
        "generated_files",
        "generated_file_hashes",
        "dependency_closure",
        "resolved_symbols",
        "toolchain",
    }
    manifest_format = manifest.get("format_version")
    if (
        manifest_format not in {2, 3}
        or manifest.get("resolved_commit") != commit
        or not required <= manifest.keys()
        or (
            manifest_format == 3
            and not _SHA256_RE.fullmatch(str(manifest.get("source_content_sha256", "")))
        )
        or not _SHA256_RE.fullmatch(str(manifest.get("descriptor_sha256", "")))
    ):
        raise SchemaVerificationError("Generated schema manifest is incomplete or incompatible.")
    return manifest


def _verify_hashes(root: Path, manifest: dict[str, object]) -> None:
    descriptor = root / "descriptor.desc"
    if (
        descriptor.is_symlink()
        or not descriptor.is_file()
        or _sha256(descriptor) != manifest["descriptor_sha256"]
    ):
        raise SchemaVerificationError(
            "Generated schema descriptor hash does not match its manifest."
        )
    hashes = manifest["generated_file_hashes"]
    files = manifest["generated_files"]
    if (
        not isinstance(hashes, dict)
        or not isinstance(files, list)
        or sorted(hashes) != sorted(map(str, files))
    ):
        raise SchemaVerificationError(
            "Generated schema manifest has inconsistent generated-file hashes."
        )
    for relative, expected in hashes.items():
        path = _cache_file(root, str(relative))
        if not _SHA256_RE.fullmatch(str(expected)) or _sha256(path) != expected:
            raise SchemaVerificationError(f"Generated schema cache is corrupt: {relative}")


def _cache_file(root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if (
        candidate.is_absolute()
        or not candidate.parts
        or any(part in {"", ".", ".."} for part in candidate.parts)
    ):
        raise SchemaVerificationError(f"Generated schema cache path is unsafe: {relative}")
    path = root / candidate
    try:
        path.resolve(strict=False).relative_to(root.resolve())
    except ValueError as exc:
        raise SchemaVerificationError(f"Generated schema cache path is unsafe: {relative}") from exc
    current = root
    for part in candidate.parts:
        current /= part
        if current.is_symlink():
            raise SchemaVerificationError(f"Generated schema cache path is unsafe: {relative}")
    if not path.is_file():
        raise SchemaVerificationError(f"Generated schema cache is corrupt: {relative}")
    return path


def _verify_contract(root: Path, manifest: dict[str, object]) -> tuple[str, ...]:
    features = tuple(map(str, manifest["required_features"]))
    declared = requirements_for(*features)
    modules = set(map(str, manifest["generated_files"]))
    required_module_files = {f"python/{module}.py" for module in declared.modules}
    if not required_module_files <= modules:
        missing = sorted(required_module_files - modules)
        raise SchemaVerificationError(
            f"Generated cache is missing required modules: {', '.join(missing)}"
        )
    symbols = manifest["resolved_symbols"]
    closure = manifest["dependency_closure"]
    if not isinstance(symbols, dict) or not isinstance(closure, list):
        raise SchemaVerificationError(
            "Generated schema manifest has invalid symbol or dependency closure data."
        )
    missing_symbols = set(declared.symbols) - set(map(str, symbols))
    if missing_symbols:
        raise SchemaVerificationError(
            "Generated cache is missing required symbols: " + ", ".join(sorted(missing_symbols))
        )
    if len(closure) != len(set(map(str, closure))):
        raise SchemaVerificationError("Generated dependency closure is not deterministic.")
    return tuple(declared.modules)


def _verify_legacy_source(cache: SdkCache, commit: str, manifest: dict[str, object]) -> None:
    source_manifest_path = cache.sdk_path(commit) / "download-manifest.json"
    if source_manifest_path.is_symlink():
        raise SchemaVerificationError("SDK source manifest is unavailable or invalid.")
    try:
        source = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SchemaVerificationError("SDK source manifest is unavailable or invalid.") from exc
    if (
        source.get("resolved_commit") != commit
        or manifest.get("source_repository") != source.get("source_repository")
        or manifest.get("requested_ref") != source.get("requested_ref")
    ):
        raise SchemaVerificationError(
            "Generated schema source metadata does not match the staged SDK."
        )


def _verify_toolchain(manifest: dict[str, object]) -> None:
    toolchain = manifest.get("toolchain")
    if not isinstance(toolchain, dict):
        raise SchemaVerificationError("Generated schema manifest has no toolchain record.")
    required_toolchain = {"grpcio_tools", "protoc", "protobuf", "python"}
    if not required_toolchain <= set(toolchain) or not all(
        isinstance(toolchain[key], str) and toolchain[key] for key in required_toolchain
    ):
        raise SchemaVerificationError(
            "Generated schema manifest has an incomplete toolchain record."
        )
    import google.protobuf

    if (
        toolchain["protobuf"] != google.protobuf.__version__
        or toolchain["python"] != sys.version.split()[0]
    ):
        raise SchemaVerificationError(
            "Generated schema toolchain is incompatible with this Python environment."
        )
    # grpcio-tools is an installation-time dependency.  If it is available,
    # validate the exact compiler versions; otherwise a verified generated
    # cache remains usable by the normal runtime package.
    try:
        current_grpc_tools = version("grpcio-tools")
        current_protoc = subprocess.run(
            [sys.executable, "-m", "grpc_tools.protoc", "--version"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (PackageNotFoundError, subprocess.CalledProcessError):
        return
    if toolchain["grpcio_tools"] != current_grpc_tools or toolchain["protoc"] != current_protoc:
        raise SchemaVerificationError(
            "Generated schema compiler version is incompatible with this cache."
        )


def _atomic_write_pointer(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        if not path.is_file() or path.is_symlink():
            raise SchemaVerificationError(f"Active schema pointer is unsafe: {path}")
    descriptor, temporary_name = mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as target:
            descriptor = -1
            json.dump(payload, target, indent=2, sort_keys=True)
            target.write("\n")
            target.flush()
            os.fsync(target.fileno())
        temporary.replace(path)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)


def _read_active_pointer(cache: SdkCache) -> str | None:
    path = cache.active_schema_manifest_path
    if not path.exists() and not path.is_symlink():
        return None
    if not path.is_file() or path.is_symlink():
        raise SchemaVerificationError(f"Active schema pointer is unsafe: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return require_full_commit(str(payload["resolved_commit"]))
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise SchemaVerificationError(f"Active schema pointer is invalid: {path}") from exc


def active_schema_commit(*, cache: SdkCache | None = None) -> str:
    """Return the independently active schema revision.

    Before an explicit schema pointer exists, a generated cache matching the
    active SDK remains a read-only legacy fallback.
    """
    cache = cache or SdkCache.default()
    commit = _read_active_pointer(cache)
    if commit is not None:
        return commit
    from polar_ble_tools.sdk_tools.downloader import sdk_status

    legacy_commit = sdk_status(cache=cache).active_commit
    if (
        legacy_commit is not None
        and (cache.generated_path(legacy_commit) / GENERATED_MANIFEST).is_file()
    ):
        return legacy_commit
    raise SchemaVerificationError(
        "No active generated schemas are installed. Run: polar-ble sdk install"
    )


def schema_status(*, cache: SdkCache | None = None) -> SchemaStatus:
    cache = cache or SdkCache.default()
    installed: list[str] = []
    if cache.generated_root.is_dir() and not cache.generated_root.is_symlink():
        for path in cache.generated_root.iterdir():
            try:
                commit = require_full_commit(path.name)
            except ValueError:
                continue
            if path.is_dir() and not path.is_symlink() and (path / GENERATED_MANIFEST).is_file():
                installed.append(commit)
    try:
        active = active_schema_commit(cache=cache)
        manifest = _read_manifest(cache.generated_path(active), active)
    except SchemaVerificationError as exc:
        return SchemaStatus(None, tuple(sorted(installed)), None, False, str(exc))
    manifest_format = int(manifest["format_version"])
    return SchemaStatus(
        active,
        tuple(sorted(installed)),
        manifest_format,
        manifest_format >= 3,
    )


def activate_schemas(commit: str, *, cache: SdkCache | None = None) -> None:
    cache = cache or SdkCache.default()
    try:
        commit = require_full_commit(commit)
    except ValueError as exc:
        raise SchemaVerificationError(
            "Schema activation requires a full lowercase 40-character commit SHA."
        ) from exc
    from polar_ble_tools.schemas.errors import SchemaUnavailableError
    from polar_ble_tools.schemas.runtime import schema_activation_manager

    try:
        schema_activation_manager(cache).ensure_activatable(commit)
    except SchemaUnavailableError as exc:
        raise SchemaVerificationError(str(exc)) from exc
    verify_schemas(commit=commit, cache=cache)
    _atomic_write_pointer(
        cache.active_schema_manifest_path,
        {"format_version": 1, "resolved_commit": commit},
    )


def schema_provenance(
    *, commit: str | None = None, cache: SdkCache | None = None
) -> SchemaProvenance:
    cache = cache or SdkCache.default()
    commit = commit or active_schema_commit(cache=cache)
    verify_schemas(commit=commit, cache=cache)
    manifest = _read_manifest(cache.generated_path(commit), commit)
    return SchemaProvenance(
        resolved_commit=commit,
        manifest_format=int(manifest["format_version"]),
        descriptor_sha256=str(manifest["descriptor_sha256"]),
        source_content_sha256=(
            str(manifest["source_content_sha256"])
            if manifest.get("source_content_sha256") is not None
            else None
        ),
    )


def _verify_imports(root: Path, modules: tuple[str, ...]) -> None:
    python_root = root / "python"
    if python_root.is_symlink() or not python_root.is_dir():
        raise SchemaVerificationError("Generated schema cache is missing its Python root.")
    # Verification is an isolated import check. Do not reuse an already-loaded
    # generated module from another cache revision, and restore the caller's
    # process state after temporary imports complete.
    prior_modules: dict[str, object] = {}
    for name, candidate in tuple(sys.modules.items()):
        module_file = getattr(candidate, "__file__", None)
        if module_file:
            try:
                Path(module_file).resolve().relative_to(python_root.resolve())
            except ValueError:
                pass
            else:
                prior_modules[name] = sys.modules.pop(name)
    for name in modules:
        if name in sys.modules:
            prior_modules[name] = sys.modules.pop(name)
    sys.path.insert(0, str(python_root))
    try:
        for name in modules:
            imported = importlib.import_module(name)
            module_file = getattr(imported, "__file__", None)
            if module_file is None or not Path(module_file).resolve().is_relative_to(
                python_root.resolve()
            ):
                raise SchemaVerificationError(
                    f"Generated module was imported outside the active cache: {name}"
                )
    except (ImportError, ValueError) as exc:
        if isinstance(exc, SchemaVerificationError):
            raise
        raise SchemaVerificationError(f"Generated module cannot be imported: {name}") from exc
    finally:
        sys.path.remove(str(python_root))
        # Verification must not pin generated modules or stale sibling imports.
        for name, candidate in tuple(sys.modules.items()):
            module_file = getattr(candidate, "__file__", None)
            if module_file and Path(module_file).resolve().is_relative_to(python_root.resolve()):
                del sys.modules[name]
        sys.modules.update(prior_modules)


def verify_schemas(*, commit: str | None = None, cache: SdkCache | None = None) -> Path:
    cache = cache or SdkCache.default()
    if commit is None:
        commit = active_schema_commit(cache=cache)
    try:
        commit = require_full_commit(commit)
    except ValueError as exc:
        raise SchemaVerificationError(
            "Schema verification requires a full lowercase 40-character commit SHA."
        ) from exc
    if cache.generated_root.is_symlink():
        raise SchemaVerificationError("Generated schema cache root is unsafe.")
    root = cache.generated_path(commit)
    manifest = _read_manifest(root, commit)
    features = tuple(map(str, manifest["required_features"]))
    if features == ("setup", "passive", "bpb"):
        try:
            reconcile_schema_requirements(features=features)
        except SchemaRequirementDriftError as exc:
            raise SchemaVerificationError(
                "Generated schema requirements drift from project consumers."
            ) from exc
    if manifest["format_version"] == 2:
        _verify_legacy_source(cache, commit, manifest)
    _verify_toolchain(manifest)
    _verify_hashes(root, manifest)
    modules = _verify_contract(root, manifest)
    _verify_imports(root, modules)
    return root / "python"


def verify_active_schemas(*, cache: SdkCache | None = None) -> Path:
    return verify_schemas(cache=cache)
