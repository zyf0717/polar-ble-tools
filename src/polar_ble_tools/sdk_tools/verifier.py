from __future__ import annotations

import hashlib
import importlib
import json
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from polar_ble_tools.schemas.cache import SdkCache
from polar_ble_tools.schemas.requirements import requirements_for
from polar_ble_tools.sdk_tools.downloader import active_sdk_source
from polar_ble_tools.sdk_tools.generator import GENERATED_MANIFEST
from polar_ble_tools.sdk_tools.requirement_scan import (
    SchemaRequirementDriftError,
    reconcile_schema_requirements,
)


class SchemaVerificationError(RuntimeError):
    """Raised when local generated schemas are missing or invalid."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_manifest(root: Path, commit: str) -> dict[str, object]:
    manifest_path = root / GENERATED_MANIFEST
    if not manifest_path.is_file():
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
    if (
        manifest.get("format_version") != 2
        or manifest.get("resolved_commit") != commit
        or not required <= manifest.keys()
    ):
        raise SchemaVerificationError(
            "Generated schema manifest is incomplete or incompatible with the active SDK."
        )
    return manifest


def _verify_hashes(root: Path, manifest: dict[str, object]) -> None:
    descriptor = root / "descriptor.desc"
    if not descriptor.is_file() or _sha256(descriptor) != manifest["descriptor_sha256"]:
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
        path = root / str(relative)
        if not path.is_file() or _sha256(path) != expected:
            raise SchemaVerificationError(f"Generated schema cache is corrupt: {relative}")


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


def _verify_source_and_toolchain(cache: SdkCache, commit: str, manifest: dict[str, object]) -> None:
    source_manifest_path = cache.sdk_path(commit) / "download-manifest.json"
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


def _verify_imports(root: Path, modules: tuple[str, ...]) -> None:
    python_root = root / "python"
    if not python_root.is_dir():
        raise SchemaVerificationError("Generated schema cache is missing its Python root.")
    # Verification is an isolated import check. Do not reuse an already-loaded
    # generated module from another cache revision, and restore the caller's
    # process state after temporary imports complete.
    prior_modules = {name: sys.modules.pop(name) for name in modules if name in sys.modules}
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
        commit, _ = active_sdk_source(cache=cache)
    # Atomic sdk install validates a staged revision without activating it.
    source_manifest = cache.sdk_path(commit) / "download-manifest.json"
    if not source_manifest.is_file():
        raise SchemaVerificationError("Requested generated cache has no verified SDK source.")
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
    _verify_source_and_toolchain(cache, commit, manifest)
    _verify_hashes(root, manifest)
    modules = _verify_contract(root, manifest)
    _verify_imports(root, modules)
    return root / "python"


def verify_active_schemas(*, cache: SdkCache | None = None) -> Path:
    return verify_schemas(cache=cache)
