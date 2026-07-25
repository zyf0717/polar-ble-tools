from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

from polar_ble_tools.schemas.cache import SdkCache
from polar_ble_tools.sdk_tools.generator import (
    GENERATED_MANIFEST,
    GENERATION_PLAN,
    generate_schemas,
)
from polar_ble_tools.sdk_tools.schema_decoder import SchemaGenerationPlan

COMMIT = "d" * 40


def _write_source(cache: SdkCache) -> Path:
    root = cache.sdk_path(COMMIT)
    source = root / "source"
    proto = source / "proto"
    proto.mkdir(parents=True)
    (source / "Polar_SDK_License.txt").write_text("licence\n", encoding="utf-8")
    (root / "Polar_SDK_License.txt").write_text("licence\n", encoding="utf-8")
    (root / "download-manifest.json").write_text(
        json.dumps(
            {
                "source_repository": "user-supplied",
                "requested_ref": "toy-source",
                "resolved_commit": COMMIT,
            }
        ),
        encoding="utf-8",
    )
    (proto / "base.proto").write_text(
        'syntax = "proto3";\npackage toy;\nmessage Base { string value = 1; }\n',
        encoding="utf-8",
    )
    (proto / "child.proto").write_text(
        'syntax = "proto3";\npackage toy;\nimport "base.proto";\nmessage Child { Base base = 1; }\n',
        encoding="utf-8",
    )
    (proto / "unused.proto").write_text(
        'syntax = "proto3";\npackage toy;\nmessage Unused { string value = 1; }\n',
        encoding="utf-8",
    )
    return source


def test_generator_writes_only_the_closure_and_a_complete_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import polar_ble_tools.sdk_tools.generator as generator

    cache = SdkCache(tmp_path / "cache")
    source = _write_source(cache)
    plan = SchemaGenerationPlan(
        features=("toy",),
        root_files=("child.proto",),
        dependency_closure=("base.proto", "child.proto"),
        resolved_symbols={"toy.Child": "child.proto"},
    )
    monkeypatch.setattr(generator, "decode_schema_requirements", lambda *_args, **_kwargs: plan)

    first = generate_schemas(
        resolved_commit=COMMIT,
        source=source,
        features=("toy",),
        cache=cache,
    )
    root = cache.generated_path(COMMIT)
    manifest = json.loads((root / GENERATED_MANIFEST).read_text(encoding="utf-8"))

    assert first.python_path == root / "python"
    assert sorted(manifest["generated_files"]) == ["python/base_pb2.py", "python/child_pb2.py"]
    assert not (first.python_path / "unused_pb2.py").exists()
    assert manifest["dependency_closure"] == ["base.proto", "child.proto"]
    assert manifest["resolved_symbols"] == {"toy.Child": "child.proto"}
    assert manifest["descriptor_sha256"]
    assert set(manifest["toolchain"]) == {"grpcio_tools", "protoc", "protobuf", "python"}
    assert sorted(manifest["generated_file_hashes"]) == manifest["generated_files"]
    assert (root / "Polar_SDK_License.txt").is_file()
    assert json.loads((root / GENERATION_PLAN).read_text(encoding="utf-8")) == plan.to_dict()

    sys.path.insert(0, str(first.python_path))
    try:
        assert importlib.import_module("child_pb2").Child.__name__ == "Child"
    finally:
        sys.path.remove(str(first.python_path))
        sys.modules.pop("base_pb2", None)
        sys.modules.pop("child_pb2", None)

    second = generate_schemas(
        resolved_commit=COMMIT,
        source=source,
        features=("toy",),
        cache=cache,
    )
    assert second.plan.to_dict() == first.plan.to_dict()
    assert not cache.generated_path(COMMIT).with_name(f".{COMMIT}.previous").exists()
