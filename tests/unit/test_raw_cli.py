from __future__ import annotations

import json
from pathlib import Path

from polar_ble_tools.commands.raw import raw_main


def _inventory(tmp_path: Path) -> Path:
    path = tmp_path / "devices.yaml"
    path.write_text("polar:\n  - AA:BB:CC:DD:EE:FF\n", encoding="utf-8")
    return path


def test_raw_cli_rejects_unauthorized_device(tmp_path: Path, capsys) -> None:
    status = raw_main(
        ["--mac-address", "11:22:33:44:55:66", "--devices-file", str(_inventory(tmp_path)), "list"]
    )
    assert status == 2
    assert "not authorized" in capsys.readouterr().err


def test_raw_collect_delegates_to_collection_api(monkeypatch, capsys) -> None:
    class Result:
        ok = True

        def to_jsonable(self):
            return {"fetched": 1}

    async def fake_collect(*args, **kwargs):
        assert args == ("AA:BB:CC:DD:EE:FF",)
        assert kwargs["record_types"] == {"ACC"}
        assert kwargs["delete_after_collect"] is True
        return Result()

    monkeypatch.setattr("polar_ble_tools.commands.raw.collect_raw_recordings", fake_collect)
    status = raw_main(
        [
            "--mac-address",
            "AA:BB:CC:DD:EE:FF",
            "collect",
            "--type",
            "ACC",
            "--delete-after-collect",
        ]
    )
    assert status == 0
    assert json.loads(capsys.readouterr().out) == {"fetched": 1}


def test_raw_list_delegates_to_collection_api(monkeypatch, tmp_path: Path, capsys) -> None:
    class Entry:
        path = "/U/0/20260725/R/112233/ACC0.REC"
        record_type = "ACC0"
        size = 77
        started_at = None

    async def fake_list(*args, **kwargs):
        assert args == ("AA:BB:CC:DD:EE:FF",)
        assert kwargs == {}
        return [Entry()]

    monkeypatch.setattr("polar_ble_tools.commands.raw.list_raw_recordings", fake_list)
    status = raw_main(
        ["--mac-address", "AA:BB:CC:DD:EE:FF", "--devices-file", str(_inventory(tmp_path)), "list"]
    )
    assert status == 0
    assert json.loads(capsys.readouterr().out)["listed"] == 1


def test_raw_start_parses_settings_and_emits_stable_json(monkeypatch, capsys) -> None:
    class Result:
        def to_jsonable(self):
            return {"active": True, "operation": "start", "recording_type": "ACC"}

    async def fake_start(*args, **kwargs):
        assert args == ("AA:BB:CC:DD:EE:FF", "ACC", {"SAMPLE_RATE": 25})
        assert kwargs == {}
        return Result()

    monkeypatch.setattr("polar_ble_tools.commands.raw.start_recording", fake_start)

    status = raw_main(
        [
            "--mac-address",
            "AA:BB:CC:DD:EE:FF",
            "start",
            "--type",
            "ACC",
            "--setting",
            "sample-rate=0x19",
        ]
    )

    assert status == 0
    assert json.loads(capsys.readouterr().out)["recording_type"] == "ACC"


def test_raw_trigger_rejects_duplicate_settings_before_api_call(monkeypatch, capsys) -> None:
    async def fail_update(*_args, **_kwargs):
        raise AssertionError("duplicate validation must happen before the API call")

    monkeypatch.setattr("polar_ble_tools.commands.raw.update_offline_trigger", fail_update)

    status = raw_main(
        [
            "--mac-address",
            "AA:BB:CC:DD:EE:FF",
            "trigger",
            "set",
            "--mode",
            "system-start",
            "--type",
            "ACC",
            "--setting",
            "sample-rate=25",
            "--setting",
            "SAMPLE_RATE=50",
        ]
    )

    assert status == 1
    assert "Duplicate recording setting" in capsys.readouterr().err
