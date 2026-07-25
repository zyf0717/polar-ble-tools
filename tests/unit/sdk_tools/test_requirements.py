from __future__ import annotations

from pathlib import Path

import pytest

from polar_ble_tools.schemas.requirements import SchemaFeatureRequirement, requirements_for
from polar_ble_tools.sdk_tools.requirement_scan import (
    SchemaRequirementDriftError,
    reconcile_schema_requirements,
    scan_schema_references,
)


def test_feature_requirements_are_deterministic_and_deduplicated() -> None:
    requirement = requirements_for("bpb", "setup")

    assert requirement.modules == tuple(sorted(requirement.modules))
    assert requirement.modules.count("user_physdata_pb2") == 1
    assert "protocol.PbPFtpSetSystemTimeParams" in requirement.symbols
    assert "data.PbDeviceInfo" in requirement.symbols


def test_unknown_feature_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown schema feature"):
        requirements_for("unknown")


def test_ast_scanner_finds_generated_module_and_static_symbol_references(tmp_path: Path) -> None:
    source = tmp_path / "schema_use.py"
    source.write_text(
        "from local.schemas import user_physdata_pb2 as phys\n"
        "import local.schemas.types_pb2\n"
        "value = phys.PbUserPhysData()\n",
        encoding="utf-8",
    )

    inferred = scan_schema_references([source])

    assert inferred.modules == ("types_pb2", "user_physdata_pb2")
    assert inferred.module_symbols == ("user_physdata_pb2.PbUserPhysData",)


def test_ast_scanner_finds_lazy_proxy_references(tmp_path: Path) -> None:
    source = tmp_path / "schema_proxy.py"
    source.write_text(
        'schema = _GeneratedModuleProxy("types_pb2")\nvalue = schema.PbSystemDateTime()\n',
        encoding="utf-8",
    )

    inferred = scan_schema_references([source])

    assert inferred.modules == ("types_pb2",)
    assert inferred.module_symbols == ("types_pb2.PbSystemDateTime",)


def test_requirement_reconciliation_rejects_undeclared_and_stale_references(tmp_path: Path) -> None:
    source = tmp_path / "schema_use.py"
    source.write_text("import unknown_pb2\nvalue = unknown_pb2.PbUnknown()\n", encoding="utf-8")
    requirement = SchemaFeatureRequirement(modules=("known_pb2",), symbols=("PbKnown",))

    with pytest.raises(SchemaRequirementDriftError, match="undeclared modules"):
        reconcile_schema_requirements(
            paths=[source],
            requirement=requirement,
            module_exceptions={},
            symbol_exceptions={},
        )
