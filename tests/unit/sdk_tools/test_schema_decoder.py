from __future__ import annotations

import pytest

from polar_ble_tools.schemas.requirements import SchemaFeatureRequirement
from polar_ble_tools.sdk_tools.schema_decoder import (
    SchemaResolutionError,
    decode_schema_requirements,
)


def _inspection() -> dict[str, object]:
    return {
        "files": [{"name": "common.proto"}, {"name": "feature.proto"}],
        "messages": [
            {"name": "data.PbCommon", "file": "common.proto"},
            {"name": "data.PbFeature", "file": "feature.proto"},
        ],
        "enums": [],
        "dependencies": {"common.proto": [], "feature.proto": ["common.proto"]},
    }


def test_decoder_resolves_modules_symbols_and_dependency_order() -> None:
    plan = decode_schema_requirements(
        _inspection(),
        requirement=SchemaFeatureRequirement(
            modules=("feature_pb2",),
            symbols=("data.PbCommon",),
        ),
    )

    assert plan.root_files == ("common.proto", "feature.proto")
    assert plan.dependency_closure == ("common.proto", "feature.proto")
    assert plan.resolved_symbols == {"data.PbCommon": "common.proto"}


def test_decoder_rejects_missing_symbols_and_modules() -> None:
    with pytest.raises(SchemaResolutionError, match="Required symbol does not exist"):
        decode_schema_requirements(
            _inspection(),
            requirement=SchemaFeatureRequirement(modules=(), symbols=("data.Missing",)),
        )
    with pytest.raises(SchemaResolutionError, match="has no source file"):
        decode_schema_requirements(
            _inspection(),
            requirement=SchemaFeatureRequirement(modules=("missing_pb2",), symbols=()),
        )
