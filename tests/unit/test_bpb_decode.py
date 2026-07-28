from __future__ import annotations

import hashlib
import json
import stat
from pathlib import Path
from types import SimpleNamespace

from google.protobuf.struct_pb2 import Struct

from polar_ble_tools.bpb_decode import (
    FAILED_STATUS,
    SUPPORTED_STATUS,
    UNSUPPORTED_STATUS,
    decode_bpb_file,
    decode_bpb_manifest,
    decode_passive_manifest,
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
        raise SchemaUnavailableError("run: polar-ble sdk install")

    monkeypatch.setattr("polar_ble_tools.bpb_decode.schemas.require_modules", unavailable)

    result = decode_bpb_file(path, device_path="/U/0/20260625/DSUM/DSUM.BPB")

    assert result.status == FAILED_STATUS
    assert result.schema_id == "daily_summary"
    assert "polar-ble sdk install" in str(result.error)


def test_bpb_cli_decodes_unknown_payload_without_schema_cache(tmp_path: Path, capsys) -> None:
    path = tmp_path / "UNKNOWN.BPB"
    path.write_bytes(b"raw")

    assert bpb_main(["decode", "--path", str(path), "--device-path", "/SYS/UNKNOWN.BPB"]) == 0
    assert '"status": "unsupported"' in capsys.readouterr().out


def test_bpb_decoder_rejects_symlink_input(tmp_path: Path) -> None:
    target = tmp_path / "target.BPB"
    target.write_bytes(b"raw")
    link = tmp_path / "link.BPB"
    link.symlink_to(target)

    result = decode_bpb_file(link, device_path="/SYS/UNKNOWN.BPB")

    assert result.status == FAILED_STATUS
    assert result.error_code == "unsafe_input"


def test_bpb_decoder_enforces_bounded_input(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "UNKNOWN.BPB"
    path.write_bytes(b"raw")
    monkeypatch.setattr("polar_ble_tools.bpb_decode.core.MAX_BPB_BYTES", 2)

    result = decode_bpb_file(path, device_path="/SYS/UNKNOWN.BPB")

    assert result.status == FAILED_STATUS
    assert result.error_code == "input_too_large"


def test_manifest_decode_rejects_raw_evidence_mismatch(tmp_path: Path) -> None:
    raw = tmp_path / "UNKNOWN.BPB"
    raw.write_bytes(b"raw")
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(
        json.dumps(
            {
                "status": "fetched",
                "local_path": raw.name,
                "device_path": "/SYS/UNKNOWN.BPB",
                "fetched_size": 3,
                "sha256": "0" * 64,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = decode_bpb_manifest(manifest)

    assert result.failed == 1
    assert result.results[0].error_code == "source_evidence_mismatch"


def test_passive_decode_enriches_autos_date_and_schema_provenance(
    tmp_path: Path, monkeypatch
) -> None:
    from polar_ble_tools.passive_data.storage import PassiveFileStore

    store = PassiveFileStore(tmp_path)
    message = Struct()
    message.update({"day": {"year": 2026, "month": 6, "day": 25}})
    payload = message.SerializeToString()
    entry = store.persist_file(
        "AA:BB:CC:DD:EE:FF",
        domain="automatic_samples",
        device_path="/U/0/AUTOS/AUTOS001.BPB",
        device_size=len(payload),
        payload=payload,
        logical_date=None,
    )
    schema = SimpleNamespace(
        schema_id="automatic_sample_sessions",
        message_class=Struct,
    )
    monkeypatch.setattr("polar_ble_tools.bpb_decode.core.schema_for_bpb", lambda **_kwargs: schema)
    monkeypatch.setattr(
        "polar_ble_tools.bpb_decode.core.schema_activation_manager",
        lambda: SimpleNamespace(active_commit="a" * 40),
    )
    monkeypatch.setattr(
        "polar_ble_tools.bpb_decode.core.schema_provenance",
        lambda **_kwargs: SimpleNamespace(
            resolved_commit="a" * 40,
            manifest_format=3,
            descriptor_sha256="b" * 64,
        ),
    )

    result = decode_passive_manifest(store.manifest_path(entry.device_id))

    assert result.decoded == 1
    decoded = result.results[0]
    assert decoded.status == SUPPORTED_STATUS
    assert decoded.logical_date == "2026-06-25"
    assert decoded.logical_date_source == "payload.day"
    rows = store.read_manifest(entry.device_id)
    assert len(rows) == 2
    assert rows[-1].schema_version == 2
    assert rows[-1].logical_date == "2026-06-25"
    assert rows[-1].sha256 == hashlib.sha256(payload).hexdigest()
    assert rows[-1].schema_commit == "a" * 40
    assert rows[-1].decoded_sha256 == decoded.decoded_sha256
    assert stat.S_IMODE(Path(str(decoded.decoded_path)).stat().st_mode) == 0o600


def test_passive_decode_rejects_payload_and_path_date_mismatch(tmp_path: Path, monkeypatch) -> None:
    from polar_ble_tools.passive_data.storage import PassiveFileStore

    store = PassiveFileStore(tmp_path)
    message = Struct()
    message.update({"date": {"year": 2026, "month": 6, "day": 24}})
    payload = message.SerializeToString()
    entry = store.persist_file(
        "AA:BB:CC:DD:EE:FF",
        domain="daily_summary",
        device_path="/U/0/20260625/DSUM/DSUM.BPB",
        device_size=len(payload),
        payload=payload,
        logical_date="2026-06-25",
    )
    monkeypatch.setattr(
        "polar_ble_tools.bpb_decode.core.schema_for_bpb",
        lambda **_kwargs: SimpleNamespace(schema_id="daily_summary", message_class=Struct),
    )
    monkeypatch.setattr(
        "polar_ble_tools.bpb_decode.core.schema_activation_manager",
        lambda: SimpleNamespace(active_commit="a" * 40),
    )
    monkeypatch.setattr(
        "polar_ble_tools.bpb_decode.core.schema_provenance",
        lambda **_kwargs: SimpleNamespace(
            resolved_commit="a" * 40,
            manifest_format=3,
            descriptor_sha256="b" * 64,
        ),
    )

    result = decode_passive_manifest(store.manifest_path(entry.device_id))

    assert result.failed == 1
    assert result.results[0].error_code == "logical_date_mismatch"
    assert len(store.read_manifest(entry.device_id)) == 1
