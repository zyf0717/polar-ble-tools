from __future__ import annotations

from pathlib import Path

from polar_ble_tools.bpb_decode import (
    FAILED_STATUS,
    UNSUPPORTED_STATUS,
    decode_bpb_file,
    schema_for_bpb,
)
from polar_ble_tools.commands.bpb import bpb_main
from polar_ble_tools.schemas.errors import SchemaUnavailableError


def test_bpb_registry_maps_known_paths_without_loading_schemas() -> None:
    schema = schema_for_bpb(
        device_path="/U/0/20260625/DSUM/DSUM.BPB",
        local_path="DSUM.BPB",
    )

    assert schema is not None
    assert schema.schema_id == "daily_summary"
    assert schema_for_bpb(device_path="/SYS/UNKNOWN.BPB", local_path="UNKNOWN.BPB") is None


def test_unknown_bpb_is_reported_without_schema_cache(tmp_path: Path) -> None:
    path = tmp_path / "UNKNOWN.BPB"
    path.write_bytes(b"raw")

    result = decode_bpb_file(path, device_path="/SYS/UNKNOWN.BPB")

    assert result.status == UNSUPPORTED_STATUS
    assert result.file_size == 3


def test_known_bpb_reports_actionable_missing_schema_without_crashing(
    tmp_path: Path, monkeypatch
) -> None:
    path = tmp_path / "DSUM.BPB"
    path.write_bytes(b"raw")

    def unavailable(*modules: str):
        raise SchemaUnavailableError("run: polar-ble sdk install --accept-license")

    monkeypatch.setattr("polar_ble_tools.bpb_decode.schemas.require_modules", unavailable)

    result = decode_bpb_file(path, device_path="/U/0/20260625/DSUM/DSUM.BPB")

    assert result.status == FAILED_STATUS
    assert result.schema_id == "daily_summary"
    assert "polar-ble sdk install --accept-license" in str(result.error)


def test_bpb_cli_decodes_unknown_payload_without_schema_cache(tmp_path: Path, capsys) -> None:
    path = tmp_path / "UNKNOWN.BPB"
    path.write_bytes(b"raw")

    assert bpb_main(["decode", "--path", str(path), "--device-path", "/SYS/UNKNOWN.BPB"]) == 0
    assert '"status": "unsupported"' in capsys.readouterr().out
