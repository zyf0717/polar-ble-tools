from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from polar_ble_tools.schemas.cache import SdkCache
from polar_ble_tools.sdk_tools.discovery import discover_proto_layout
from polar_ble_tools.sdk_tools.downloader import SUPPORTED_SDK_COMMIT, sdk_status
from polar_ble_tools.sdk_tools.generator import (
    GENERATED_MANIFEST,
    generate_schemas,
)
from polar_ble_tools.sdk_tools.inspector import inspect_descriptor_set
from polar_ble_tools.sdk_tools.proto_reader import build_descriptor_set
from polar_ble_tools.sdk_tools.schema_decoder import decode_schema_requirements
from polar_ble_tools.sdk_tools.verifier import activate_schemas, verify_schemas

PINNED_SDK_COMMIT = SUPPORTED_SDK_COMMIT
SDK_PATH = os.environ.get("POLAR_BLE_SDK_PATH")


def _pinned_sdk_source() -> Path:
    if SDK_PATH is not None:
        source = Path(SDK_PATH).resolve()
    else:
        cache = SdkCache.default()
        status = sdk_status(cache=cache)
        if status.active_commit != PINNED_SDK_COMMIT:
            pytest.fail(
                "Install the licensed pinned SDK or set POLAR_BLE_SDK_PATH before "
                "running SDK contract tests."
            )
        source = cache.sdk_path(PINNED_SDK_COMMIT) / "source"
    manifest_path = source.parent / "download-manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        pytest.fail(f"SDK contract source has no valid provenance manifest: {manifest_path}: {exc}")
    assert source.is_dir()
    assert not (source / ".git").exists()
    assert manifest["requested_ref"] == PINNED_SDK_COMMIT
    assert manifest["resolved_commit"] == PINNED_SDK_COMMIT
    assert manifest["source_repository"] == "https://github.com/polarofficial/polar-ble-sdk.git"
    # Older managed caches predate explicit support-tier fields; the supported
    # SHA above remains the contract. Fresh caches record this explicitly.
    assert manifest.get("supported_commit", PINNED_SDK_COMMIT) == PINNED_SDK_COMMIT
    assert manifest.get("support_tier", "pinned") == "pinned"
    return source


def test_pinned_sdk_descriptor_inventory() -> None:
    sdk_path = _pinned_sdk_source()
    layout = discover_proto_layout(sdk_path)
    with TemporaryDirectory(prefix="polar-ble-sdk-contract-") as temporary:
        descriptor_set = build_descriptor_set(layout, Path(temporary) / "all.desc")
    inspection = inspect_descriptor_set(descriptor_set)

    assert len(layout.roots) == 2
    assert len(inspection["files"]) == 31
    assert len(inspection["messages"]) >= 200
    assert len(inspection["enums"]) >= 100
    assert any(item["name"] == "data.PbUserPhysData" for item in inspection["messages"])
    assert any(item["name"] == "data.PbDailySummary" for item in inspection["messages"])

    plan = decode_schema_requirements(inspection, features=("setup", "passive", "bpb"))
    assert plan.dependency_closure == (
        "google/protobuf/descriptor.proto",
        "types.proto",
        "act_samples.proto",
        "nanopb.proto",
        "ppi_samples.proto",
        "automatic_samples.proto",
        "dailysummary.proto",
        "structures.proto",
        "device.proto",
        "nightly_recovery.proto",
        "pftp_request.proto",
        "sensor_data_log.proto",
        "types_proto3.proto",
        "sleep_skin_temperature_result.proto",
        "sleepanalysisresult.proto",
        "temperature_measurement_period.proto",
        "user_devset.proto",
        "user_id.proto",
        "user_physdata.proto",
    )


def test_pinned_sdk_generation_and_verification_contract(tmp_path: Path) -> None:
    source = _pinned_sdk_source()
    cache = SdkCache.default()
    expected_source = cache.sdk_path(PINNED_SDK_COMMIT) / "source"
    if source != expected_source:
        pytest.fail(
            "Full generation contract requires the pinned SDK in the managed "
            f"cache: expected {expected_source}, got {source}."
        )

    first = generate_schemas(
        resolved_commit=PINNED_SDK_COMMIT,
        source=source,
        cache=cache,
    )
    second = generate_schemas(
        resolved_commit=PINNED_SDK_COMMIT,
        source=source,
        cache=cache,
    )
    verified_root = verify_schemas(commit=PINNED_SDK_COMMIT, cache=cache)
    manifest = json.loads(
        (cache.generated_path(PINNED_SDK_COMMIT) / GENERATED_MANIFEST).read_text(encoding="utf-8")
    )

    assert first.plan.to_dict() == second.plan.to_dict()
    assert verified_root == second.python_path
    assert manifest["format_version"] == 3
    assert manifest["resolved_commit"] == PINNED_SDK_COMMIT
    assert manifest["source_content_sha256"]
    assert manifest["descriptor_sha256"]
    assert manifest["generated_files"]
    assert manifest["generated_file_hashes"]
    assert manifest["resolved_symbols"]

    detached = SdkCache(tmp_path / "detached-cache")
    detached.generated_root.mkdir(parents=True)
    shutil.copytree(
        cache.generated_path(PINNED_SDK_COMMIT),
        detached.generated_path(PINNED_SDK_COMMIT),
    )
    activate_schemas(PINNED_SDK_COMMIT, cache=detached)
    assert verify_schemas(cache=detached) == detached.generated_path(PINNED_SDK_COMMIT) / "python"
