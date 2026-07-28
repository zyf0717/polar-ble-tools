from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pytest

from polar_ble_tools.bpb_decode import SUPPORTED_STATUS, decode_bpb_file


def test_configured_private_bpb_corpus() -> None:
    manifest_text = os.environ.get("POLAR_BLE_BPB_FIXTURE_MANIFEST")
    if not manifest_text:
        pytest.skip("set POLAR_BLE_BPB_FIXTURE_MANIFEST to a private fixture manifest")
    manifest_path = Path(manifest_text).expanduser().resolve()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    fixtures = payload.get("fixtures") if isinstance(payload, dict) else None
    assert isinstance(fixtures, list) and fixtures, "fixture manifest has no fixtures"
    for fixture in fixtures:
        assert isinstance(fixture, dict)
        source = _fixture_path(manifest_path, fixture)
        result = decode_bpb_file(source, device_path=str(fixture["device_path"]))
        assert result.status == SUPPORTED_STATUS
        assert result.schema_id == fixture["expected_schema_id"]
        if "expected_raw_sha256" in fixture:
            assert result.sha256 == fixture["expected_raw_sha256"]
        if "expected_json_sha256" in fixture:
            assert _json_sha256(result.data) == fixture["expected_json_sha256"]
        for field, expected in fixture.get("expected_fields", {}).items():
            assert _field(result.data, str(field)) == expected


def _fixture_path(manifest_path: Path, fixture: dict[str, Any]) -> Path:
    source = Path(str(fixture["path"])).expanduser()
    return source.resolve() if source.is_absolute() else (manifest_path.parent / source).resolve()


def _json_sha256(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _field(value: object, dotted: str) -> object:
    current = value
    for part in dotted.split("."):
        assert isinstance(current, dict), f"{dotted} does not select an object field"
        current = current[part]
    return current
