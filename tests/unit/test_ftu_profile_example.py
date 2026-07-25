from __future__ import annotations

from polar_ble_tools.polar.setup import FtuProfile


def test_ftu_profile_example_parses_and_includes_initial_settings() -> None:
    profile = FtuProfile.from_json_file("docs/ftu-profile.example.json")

    assert profile.user_device_settings is not None
    assert profile.user_device_settings.has_changes is True
