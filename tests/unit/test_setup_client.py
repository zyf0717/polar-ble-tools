from __future__ import annotations

import asyncio
from datetime import datetime

import pytest

from polar_ble_tools.polar.setup import (
    DeviceLocation,
    PolarSetupClient,
    SetupDeviceResponseError,
    SetupPartialWriteError,
    VeritySenseFtuProfile,
)


def test_verity_ftu_sets_runtime_time_before_wear_location() -> None:
    calls: list[tuple[str, object]] = []
    client = PolarSetupClient(object())
    profile = VeritySenseFtuProfile(DeviceLocation.UPPER_ARM_LEFT)

    async def set_local_time(device_time: datetime) -> None:
        calls.append(("time", device_time))

    async def set_user_device_settings(patch: object) -> None:
        calls.append(("settings", patch))

    client.set_local_time = set_local_time
    client.set_user_device_settings = set_user_device_settings

    asyncio.run(client.do_verity_sense_first_time_use(profile))

    assert [name for name, _ in calls] == ["time", "settings"]
    device_time = calls[0][1]
    assert isinstance(device_time, datetime)
    assert device_time.tzinfo is not None
    assert device_time.utcoffset() is not None
    assert calls[1][1].device_location is DeviceLocation.UPPER_ARM_LEFT


def test_verity_ftu_reports_partial_write_after_time_update() -> None:
    client = PolarSetupClient(object())
    profile = VeritySenseFtuProfile(DeviceLocation.UPPER_ARM_LEFT)

    async def set_local_time(_device_time: datetime) -> None:
        return None

    async def set_user_device_settings(_patch: object) -> None:
        raise RuntimeError("rejected")

    client.set_local_time = set_local_time
    client.set_user_device_settings = set_user_device_settings

    with pytest.raises(SetupPartialWriteError, match="after setting device time"):
        asyncio.run(client.do_verity_sense_first_time_use(profile))


def test_verity_ftu_reports_partial_time_state_when_time_setup_fails() -> None:
    client = PolarSetupClient(object())
    profile = VeritySenseFtuProfile(DeviceLocation.UPPER_ARM_LEFT)

    async def set_local_time(_device_time: datetime) -> None:
        raise RuntimeError("rejected")

    async def set_user_device_settings(_patch: object) -> None:
        raise AssertionError("settings must not run after time setup failure")

    client.set_local_time = set_local_time
    client.set_user_device_settings = set_user_device_settings

    with pytest.raises(SetupDeviceResponseError, match="time state may be partial"):
        asyncio.run(client.do_verity_sense_first_time_use(profile))
