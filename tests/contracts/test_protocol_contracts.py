from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pytest

from polar_ble_tools.bpb_decode import UNSUPPORTED_STATUS, decode_bpb_file
from polar_ble_tools.commands.ftu import ftu_main
from polar_ble_tools.commands.main import main
from polar_ble_tools.polar._protobuf import (
    PftpCommand,
    PftpDirectoryEntry,
    decode_pftp_directory,
    encode_pftp_directory,
    encode_pftp_operation,
)
from polar_ble_tools.polar.offline import (
    OfflineRecord,
    OfflineRecordingClient,
    parse_offline_recording_path,
)
from polar_ble_tools.polar.setup import FtuProfile, SetupValidationError
from polar_ble_tools.raw_data.storage import RawRecordingStore

# These synthetic vectors lock observable protocol, manifest, and CLI
# contracts. They contain no SDK, device capture, or profile data.


def test_pftp_operation_bytes_match_contract() -> None:
    assert encode_pftp_operation(PftpCommand.GET, "/U/0/") == b"\x08\x00\x12\x05/U/0/"
    entries = [PftpDirectoryEntry(name="ACC.REC", size=123)]
    assert decode_pftp_directory(encode_pftp_directory(entries)) == entries


def test_raw_rec_retrieval_object_matches_contract() -> None:
    class Pftp:
        async def get_file(self, path: str) -> bytes:
            assert path == "/U/0/20260613/R/112233/ACC.REC"
            return b"raw-record"

    async def retrieve() -> OfflineRecord:
        entry = parse_offline_recording_path("/U/0/20260613/R/112233/ACC.REC", size=10)
        return await OfflineRecordingClient(Pftp()).fetch_record(entry)  # type: ignore[arg-type]

    assert asyncio.run(retrieve()).payload == b"raw-record"


def test_raw_record_metadata_and_manifest_contract(tmp_path: Path) -> None:
    store = RawRecordingStore(tmp_path / "raw")
    entry = parse_offline_recording_path("/U/0/20260613/R/112233/ACC.REC", size=10)

    manifest = store.persist_record(
        "AA:BB:CC:DD:EE:FF",
        entry,
        b"raw-record",
        fetched_at=datetime(2026, 6, 25, tzinfo=UTC),
    )

    assert manifest.to_jsonable() == {
        "device_id": "AABBCCDDEEFF",
        "device_path": "/U/0/20260613/R/112233/ACC.REC",
        "device_size": 10,
        "device_user_index": 0,
        "fetched_at": "2026-06-25T00:00:00Z",
        "fetched_size": 10,
        "local_path": "AABBCCDDEEFF/U0/20260613/112233/ACC.REC",
        "record_type": "ACC",
        "schema_version": 1,
        "sha256": "163a0f47135043858781f55adf44f68c277be47d6d1d5cf8d8036db6304c8701",
        "started_at": "2026-06-13T11:22:33",
        "status": "fetched",
    }
    assert store.resolve_local_path(manifest.local_path).read_bytes() == b"raw-record"
    assert sha256(b"raw-record").hexdigest() == manifest.sha256


def test_unknown_bpb_normalized_result_contract(tmp_path: Path) -> None:
    path = tmp_path / "UNKNOWN.BPB"
    path.write_bytes(b"raw")

    result = decode_bpb_file(path, device_path="/SYS/UNKNOWN.BPB").to_jsonable()
    result["local_path"] = path.name

    assert result == {
        "data": None,
        "decoded_path": None,
        "decoded_sha256": None,
        "descriptor_sha256": None,
        "device_path": "/SYS/UNKNOWN.BPB",
        "error": None,
        "error_code": None,
        "file_size": 3,
        "local_path": "UNKNOWN.BPB",
        "message_type": None,
        "logical_date": None,
        "logical_date_source": None,
        "reason": "No registered protobuf schema matches this BPB path.",
        "schema_commit": None,
        "schema_id": None,
        "schema_manifest_format": None,
        "sha256": "d7439bee24773bcbfa2d0a97947ee36227b10d1022b1a55847e928965bb6bfde",
        "status": UNSUPPORTED_STATUS,
    }


def test_ftu_validation_and_dry_run_cli_contract(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    profile = tmp_path / "profile.json"
    profile.write_text(
        json.dumps(
            {
                "gender": "FEMALE",
                "birth_date": "1988-04-03",
                "height_cm": 172.5,
                "weight_kg": 65.25,
                "max_heart_rate_bpm": 188,
                "resting_heart_rate_bpm": 58,
                "vo2_max": 44,
                "training_background": 30,
                "typical_day": "MOSTLY_STANDING",
                "sleep_goal_minutes": 480,
                "device_time": "2026-06-25T10:15:30+08:00",
            }
        ),
        encoding="utf-8",
    )

    assert ftu_main(["dry-run", "--profile", str(profile)]) == 0
    output = json.loads(capsys.readouterr().out)
    output["profile"]["path"] = "<profile>"
    assert output == {
        "operations": [
            "REQUEST_SYNCHRONIZATION",
            "INITIALIZE_SESSION",
            "START_SYNC",
            "SET_SYSTEM_TIME",
            "SET_LOCAL_TIME",
            "PUT /U/0/S/PHYSDATA.BPB",
            "PUT /U/0/USERID.BPB",
            "STOP_SYNC",
            "TERMINATE_SESSION",
        ],
        "payload_sizes": "requires generated schemas",
        "profile": {
            "fields": [
                "gender",
                "birth_date",
                "height_cm",
                "weight_kg",
                "max_heart_rate_bpm",
                "resting_heart_rate_bpm",
                "vo2_max",
                "training_background",
                "typical_day",
                "sleep_goal_minutes",
                "device_time",
            ],
            "path": "<profile>",
        },
        "valid": True,
    }

    with pytest.raises(SetupValidationError, match="height_cm") as error:
        FtuProfile.from_mapping({**json.loads(profile.read_text()), "height_cm": 80})
    assert "80" not in str(error.value)


def test_verity_ftu_dry_run_contract(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    profile = tmp_path / "verity.json"
    profile.write_text(
        json.dumps(
            {
                "device_family": "POLAR_VERITY_SENSE",
                "device_location": "UPPER_ARM_LEFT",
            }
        ),
        encoding="utf-8",
    )

    assert ftu_main(["dry-run", "--profile", str(profile)]) == 0
    output = json.loads(capsys.readouterr().out)
    output["profile"]["path"] = "<profile>"
    assert output == {
        "operations": [
            "SET_SYSTEM_TIME",
            "SET_LOCAL_TIME",
            "GET /U/0/S/UDEVSET.BPB",
            "PUT /U/0/S/UDEVSET.BPB",
        ],
        "payload_sizes": "requires generated schemas",
        "profile": {
            "fields": ["device_family", "device_location"],
            "path": "<profile>",
        },
        "valid": True,
    }


def test_primary_bpb_cli_exit_and_structured_output_contract(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "UNKNOWN.BPB"
    path.write_bytes(b"raw")

    assert main(["bpb", "decode", "--path", str(path), "--device-path", "/SYS/UNKNOWN.BPB"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == UNSUPPORTED_STATUS
    assert output["device_path"] == "/SYS/UNKNOWN.BPB"
    assert output["file_size"] == 3
