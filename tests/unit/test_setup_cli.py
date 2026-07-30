from __future__ import annotations

import json
from pathlib import Path

from polar_ble_tools.commands.ftu import ftu_main


def write_profile(path: Path, **overrides: object) -> None:
    profile = {
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
    profile.update(overrides)
    path.write_text(json.dumps(profile))


def write_verity_profile(path: Path, **overrides: object) -> None:
    profile = {
        "device_family": "POLAR_VERITY_SENSE",
        "device_location": "UPPER_ARM_LEFT",
    }
    profile.update(overrides)
    path.write_text(json.dumps(profile))


def test_ftu_dry_run_redacts_profile_values(tmp_path, capsys) -> None:
    profile = tmp_path / "profile.json"
    write_profile(profile)

    exit_code = ftu_main(["dry-run", "--profile", str(profile)])

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert exit_code == 0
    assert any("PHYSDATA.BPB" in operation for operation in output["operations"])
    assert output["profile"] == {
        "path": str(profile),
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
    }
    assert captured.err == ""


def test_ftu_dry_run_does_not_activate_generated_schemas(tmp_path, monkeypatch, capsys) -> None:
    profile = tmp_path / "profile.json"
    write_profile(profile)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("dry-run must not activate generated schemas")

    monkeypatch.setattr("polar_ble_tools.polar.setup_payloads.require_modules", fail_if_called)

    assert ftu_main(["dry-run", "--profile", str(profile)]) == 0
    assert capsys.readouterr().err == ""


def test_ftu_dry_run_validation_error_redacts_profile_values(tmp_path, capsys) -> None:
    profile = tmp_path / "profile.json"
    write_profile(profile, height_cm=80)

    exit_code = ftu_main(["dry-run", "--profile", str(profile)])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "height_cm" in captured.err
    assert "80" not in captured.err
    assert "1988-04-03" not in captured.err
    assert captured.out == ""


def test_ftu_dry_run_includes_profile_settings_without_values(tmp_path, capsys) -> None:
    profile = tmp_path / "profile.json"
    write_profile(
        profile,
        user_device_settings={
            "device_location": "UPPER_ARM_LEFT",
            "automatic_training_detection_mode": True,
            "automatic_training_detection_sensitivity": 50,
            "minimum_training_duration_seconds": 600,
        },
    )

    exit_code = ftu_main(["dry-run", "--profile", str(profile)])

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert exit_code == 0
    assert "GET /U/0/S/UDEVSET.BPB" in output["operations"]
    assert "PUT /U/0/S/UDEVSET.BPB" in output["operations"]
    assert output["profile"]["user_device_settings_fields"] == [
        "device_location",
        "automatic_training_detection_mode",
        "automatic_training_detection_sensitivity",
        "minimum_training_duration_seconds",
    ]
    assert "UPPER_ARM_LEFT" not in captured.out
    assert captured.err == ""


def test_verity_ftu_dry_run_contains_verified_time_and_settings_operations(
    tmp_path,
    capsys,
) -> None:
    profile = tmp_path / "verity.json"
    write_verity_profile(profile)

    exit_code = ftu_main(["dry-run", "--profile", str(profile)])

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert exit_code == 0
    assert output["profile"] == {
        "path": str(profile),
        "fields": ["device_family", "device_location"],
    }
    assert output["operations"] == [
        "SET_SYSTEM_TIME",
        "SET_LOCAL_TIME",
        "GET /U/0/S/UDEVSET.BPB",
        "PUT /U/0/S/UDEVSET.BPB",
    ]
    assert "UPPER_ARM_LEFT" not in captured.out
    assert captured.err == ""


def test_verity_ftu_dry_run_rejects_unsupported_pool_length(tmp_path, capsys) -> None:
    profile = tmp_path / "verity.json"
    write_verity_profile(profile, default_pool_length_meters=50.0)

    exit_code = ftu_main(["dry-run", "--profile", str(profile)])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "default_pool_length_meters" in captured.err
    assert "50" not in captured.err
    assert captured.out == ""


def test_ftu_apply_patches_profile_user_device_settings(
    tmp_path,
    capsys,
    monkeypatch,
) -> None:
    profile = tmp_path / "profile.json"
    write_profile(
        profile,
        user_device_settings={
            "device_location": "UPPER_ARM_LEFT",
            "automatic_training_detection_mode": True,
        },
    )
    calls: list[object] = []

    class FakeDevice:
        async def aclose(self) -> None:
            calls.append(("disconnect",))

    class FakeSetupClient:
        async def do_first_time_use(self, ftu_profile: object) -> None:
            calls.append(("ftu", ftu_profile))

        async def set_user_device_settings(self, patch: object) -> None:
            calls.append(("settings", patch))

    device = FakeDevice()
    setup_client = FakeSetupClient()

    async def fake_open_setup_client(mac_address: str) -> tuple[object, object]:
        calls.append(("open", mac_address))
        return device, setup_client

    monkeypatch.setattr(
        "polar_ble_tools.commands.ftu._open_setup_client",
        fake_open_setup_client,
    )

    exit_code = ftu_main(["--mac-address", "AA:BB:CC:DD:EE:FF", "apply", "--profile", str(profile)])

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert exit_code == 0
    assert output == {"ftu_applied": True, "settings_updated": True}
    assert calls[0] == ("open", "AA:BB:CC:DD:EE:FF")
    assert calls[1][0] == "ftu"
    assert calls[2][0] == "settings"
    assert calls[3] == ("disconnect",)
    assert captured.err == ""


def test_verity_ftu_apply_uses_device_specific_setup_path(
    tmp_path,
    capsys,
    monkeypatch,
) -> None:
    profile = tmp_path / "verity.json"
    write_verity_profile(profile)
    calls: list[object] = []

    class FakeDevice:
        async def aclose(self) -> None:
            calls.append(("disconnect",))

    class FakeSetupClient:
        async def do_first_time_use(self, _profile: object) -> None:
            raise AssertionError("Verity FTU must not use Loop physical-data writes.")

        async def do_verity_sense_first_time_use(self, profile: object) -> None:
            calls.append(("verity_ftu", profile))

    async def fake_open_setup_client(mac_address: str) -> tuple[object, object]:
        calls.append(("open", mac_address))
        return FakeDevice(), FakeSetupClient()

    monkeypatch.setattr(
        "polar_ble_tools.commands.ftu._open_setup_client",
        fake_open_setup_client,
    )

    exit_code = ftu_main(["--mac-address", "AA:BB:CC:DD:EE:FF", "apply", "--profile", str(profile)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out) == {
        "ftu_applied": True,
        "settings_updated": True,
    }
    assert calls[0] == ("open", "AA:BB:CC:DD:EE:FF")
    assert calls[1][0] == "verity_ftu"
    assert calls[2] == ("disconnect",)
    assert captured.err == ""
