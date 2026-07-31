from __future__ import annotations

import json
from pathlib import Path

import pytest

from polar_ble_tools.polar.setup import (
    DeviceLocation,
    FtuProfile,
    SetupValidationError,
    VeritySenseFtuProfile,
    load_ftu_profile,
)

LOOP_GEN2_PROFILE = Path("docs/loop-gen2-ftu-profile.example.json")
VERITY_SENSE_PROFILE = Path("docs/verity-sense-ftu-profile.example.json")


def test_loop_gen2_ftu_profile_example_parses_and_includes_initial_settings() -> None:
    profile = FtuProfile.from_json_file(LOOP_GEN2_PROFILE)

    assert profile.user_device_settings is not None
    assert profile.user_device_settings.has_changes is True


def test_verity_sense_ftu_profile_is_explicit_and_executable() -> None:
    raw = json.loads(VERITY_SENSE_PROFILE.read_text())
    profile = load_ftu_profile(VERITY_SENSE_PROFILE)

    assert raw == {
        "device_family": "POLAR_VERITY_SENSE",
        "device_location": "UPPER_ARM_LEFT",
    }
    assert isinstance(profile, VeritySenseFtuProfile)
    assert profile.device_location is DeviceLocation.UPPER_ARM_LEFT


def test_verity_sense_ftu_profile_rejects_pool_length_until_supported() -> None:
    with pytest.raises(SetupValidationError):
        VeritySenseFtuProfile.from_mapping(
            {
                "device_family": "POLAR_VERITY_SENSE",
                "device_location": "UPPER_ARM_LEFT",
                "default_pool_length_meters": 50.0,
            }
        )
