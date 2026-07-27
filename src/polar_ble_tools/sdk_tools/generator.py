from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory

from polar_ble_tools.schemas.cache import SdkCache
from polar_ble_tools.sdk_tools.discovery import ProtoLayout, discover_proto_layout
from polar_ble_tools.sdk_tools.downloader import active_sdk_source
from polar_ble_tools.sdk_tools.inspector import inspect_descriptor_set
from polar_ble_tools.sdk_tools.proto_reader import build_descriptor_set
from polar_ble_tools.sdk_tools.requirement_scan import reconcile_schema_requirements
from polar_ble_tools.sdk_tools.schema_decoder import (
    SchemaGenerationPlan,
    decode_schema_requirements,
)

GENERATED_MANIFEST = "generated-manifest.json"
GENERATION_PLAN = "generation-plan.json"


class SchemaGenerationError(RuntimeError):
    """Raised when selected Python schemas cannot be generated locally."""


@dataclass(frozen=True)
class GeneratedSchemaResult:
    resolved_commit: str
    python_path: Path
    manifest_path: Path
    plan: SchemaGenerationPlan


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _run_python_generator(layout: ProtoLayout, closure: tuple[str, ...], output: Path) -> None:
    try:
        from grpc_tools import protoc
    except ImportError as exc:
        raise SchemaGenerationError(
            'Schema generation requires: pip install "polar-ble-tools[sdk]"'
        ) from exc
    output.mkdir(parents=True, exist_ok=True)
    # Well-known protobuf types are supplied by the protobuf runtime, not copied
    # into the local generated cache.
    generated_sources = tuple(name for name in closure if not name.startswith("google/protobuf/"))
    result = protoc.main(
        [
            "grpc_tools.protoc",
            *(f"--proto_path={root}" for root in layout.roots),
            f"--python_out={output}",
            *generated_sources,
        ]
    )
    if result != 0:
        raise SchemaGenerationError(f"protoc Python generation failed with exit code {result}.")


def _toolchain() -> dict[str, str]:
    try:
        import google.protobuf

        grpc_tools_version = version("grpcio-tools")
    except ImportError as exc:  # pragma: no cover - exercised by generator import guard
        raise SchemaGenerationError(
            'Schema generation requires: pip install "polar-ble-tools[sdk]"'
        ) from exc
    except Exception as exc:
        raise SchemaGenerationError("Cannot determine grpcio-tools version.") from exc
    protoc = subprocess.run(
        [sys.executable, "-m", "grpc_tools.protoc", "--version"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return {
        "grpcio_tools": grpc_tools_version,
        "protoc": protoc,
        "protobuf": google.protobuf.__version__,
        "python": sys.version.split()[0],
    }


def generate_schemas(
    *,
    resolved_commit: str,
    source: Path,
    features: tuple[str, ...] = ("setup", "passive", "bpb"),
    cache: SdkCache,
) -> GeneratedSchemaResult:
    """Generate the selected schema closure for the active SDK into user cache."""
    commit = resolved_commit
    if features == ("setup", "passive", "bpb"):
        reconcile_schema_requirements(features=features)
    layout = discover_proto_layout(source)
    source_manifest = json.loads(
        (cache.sdk_path(commit) / "download-manifest.json").read_text(encoding="utf-8")
    )
    with TemporaryDirectory(prefix="polar-ble-generate-") as temporary:
        descriptor_path = Path(temporary) / "selected.desc"
        descriptor_set = build_descriptor_set(layout, descriptor_path)
        plan = decode_schema_requirements(inspect_descriptor_set(descriptor_set), features=features)
        cache.generated_root.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix=f".{commit[:12]}-", dir=cache.generated_root) as staged:
            staged_root = Path(staged) / "entry"
            python_path = staged_root / "python"
            _run_python_generator(layout, plan.dependency_closure, python_path)
            shutil.copy2(descriptor_path, staged_root / "descriptor.desc")
            plan_path = staged_root / GENERATION_PLAN
            plan_path.write_text(
                json.dumps(plan.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            generated_files = sorted(
                path.relative_to(staged_root).as_posix() for path in python_path.rglob("*_pb2.py")
            )
            manifest = {
                "format_version": 2,
                "vendor": "polar",
                "source_repository": source_manifest["source_repository"],
                "requested_ref": source_manifest["requested_ref"],
                "resolved_commit": commit,
                "generated_at": datetime.now(UTC).isoformat(),
                "toolchain": _toolchain(),
                "required_features": list(plan.features),
                "dependency_closure": list(plan.dependency_closure),
                "resolved_symbols": dict(sorted(plan.resolved_symbols.items())),
                "generated_files": generated_files,
                "generated_file_hashes": {
                    name: _sha256(staged_root / name) for name in generated_files
                },
                "descriptor_sha256": _sha256(staged_root / "descriptor.desc"),
            }
            (staged_root / GENERATED_MANIFEST).write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            target = cache.generated_path(commit)
            # Never remove a usable entry before the replacement is complete.
            # Same-filesystem rename is atomic on supported user-data stores.
            if target.exists():
                backup = target.with_name(f".{target.name}.previous")
                shutil.rmtree(backup, ignore_errors=True)
                target.replace(backup)
                try:
                    staged_root.replace(target)
                except Exception:
                    backup.replace(target)
                    raise
                shutil.rmtree(backup)
            else:
                staged_root.replace(target)
    return GeneratedSchemaResult(
        commit,
        cache.generated_path(commit) / "python",
        cache.generated_path(commit) / GENERATED_MANIFEST,
        plan,
    )


def generate_active_schemas(
    *,
    features: tuple[str, ...] = ("setup", "passive", "bpb"),
    cache: SdkCache | None = None,
) -> GeneratedSchemaResult:
    cache = cache or SdkCache.default()
    commit, source = active_sdk_source(cache=cache)
    return generate_schemas(resolved_commit=commit, source=source, features=features, cache=cache)
