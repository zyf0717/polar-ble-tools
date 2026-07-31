"""Opt-in hardware validation for the raw offline-recording path.

The test applies a caller-supplied FTU profile only to a target explicitly
listed in local ``test_devices.yaml``. It is intentionally disabled by default
and never deletes device data; the newly created ``.REC`` is retained on-device
and copied into the ignored ``.local/`` tree.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path

import pytest

from polar_ble_tools.ble.operations import prepare_device
from polar_ble_tools.device import open_polar_device
from polar_ble_tools.inventory import InventoryError, load_allowed_identifiers
from polar_ble_tools.polar.offline import base_record_type_for
from polar_ble_tools.polar.pmd import (
    PmdResponseCode,
    PmdResponseError,
    PmdSetting,
    PmdUnsupportedOperation,
    PolarDeviceDataType,
)
from polar_ble_tools.polar.setup import FtuProfile
from polar_ble_tools.raw_data.collector import RawRecordingCollector
from polar_ble_tools.raw_data.storage import RawRecordingStore

LIVE_E2E_ENV = "POLAR_BLE_LIVE_E2E"
LIVE_MAC_ENV = "POLAR_BLE_LIVE_MAC"
LIVE_PROFILE_ENV = "POLAR_BLE_LIVE_FTU_PROFILE"
LIVE_OUTPUT_ENV = "POLAR_BLE_LIVE_RAW_ROOT"
DEFAULT_OUTPUT_ROOT = Path(".local/polar-ble-live-raw")
TEST_DEVICES_FILE = Path("test_devices.yaml")
SMOKE_DURATION_SECONDS = 4.0
MATERIALIZATION_TIMEOUT_SECONDS = 35.0
CANDIDATES = (
    PolarDeviceDataType.ACC,
    PolarDeviceDataType.GYRO,
    PolarDeviceDataType.MAGNETOMETER,
    PolarDeviceDataType.PPG,
    PolarDeviceDataType.TEMPERATURE,
    PolarDeviceDataType.SKIN_TEMPERATURE,
    PolarDeviceDataType.PPI,
    PolarDeviceDataType.HR,
)
NO_SETTINGS_TYPES = {PolarDeviceDataType.PPI, PolarDeviceDataType.HR}
RECOVERABLE_START_RESPONSES = {
    PmdResponseCode.ERROR_INVALID_MEASUREMENT_TYPE,
    PmdResponseCode.ERROR_NOT_SUPPORTED,
    PmdResponseCode.ERROR_INVALID_STATE,
}


@dataclass(frozen=True)
class LiveConfig:
    mac_address: str
    profile_path: Path
    output_root: Path


def test_live_pair_ftu_record_and_fetch_raw() -> None:
    if os.environ.get(LIVE_E2E_ENV) != "1":
        pytest.skip(f"{LIVE_E2E_ENV}=1 is required.")
    config = _load_config()

    preparation = asyncio.run(
        prepare_device(
            config.mac_address,
            devices_file=TEST_DEVICES_FILE,
        )
    )
    assert preparation.readiness_verified
    assert preparation.final_connected is False
    result = asyncio.run(_run_e2e(config))
    assert result["fetched_size"] == result["device_size"]
    assert result["manifest_verified"] is True
    assert result["manifest_contains_record"] is True
    assert result["cleanup_dry_run"] is True
    print(
        "live_raw_e2e=passed "
        f"record_type={result['record_type']} fetched_bytes={result['fetched_size']}"
    )


def _load_config() -> LiveConfig:
    mac_address = os.environ.get(LIVE_MAC_ENV)
    profile_raw = os.environ.get(LIVE_PROFILE_ENV)
    if not mac_address:
        pytest.skip(f"{LIVE_MAC_ENV} is required to select one device.")
    if not profile_raw:
        pytest.skip(f"{LIVE_PROFILE_ENV} is required.")
    profile_path = Path(profile_raw)
    if not profile_path.is_file():
        raise AssertionError(f"FTU profile does not exist: {profile_path}")
    if not TEST_DEVICES_FILE.is_file():
        raise AssertionError(f"Live E2E requires a local authorized inventory: {TEST_DEVICES_FILE}")
    try:
        allowed_devices = load_allowed_identifiers(TEST_DEVICES_FILE)
    except InventoryError as exc:
        raise AssertionError(f"Invalid live test device inventory: {exc}") from exc
    if mac_address.upper() not in allowed_devices:
        raise AssertionError(
            f"Live E2E target {mac_address.upper()} is not authorized in {TEST_DEVICES_FILE}."
        )
    output_root = Path(os.environ.get(LIVE_OUTPUT_ENV, DEFAULT_OUTPUT_ROOT))
    local_root = (Path.cwd() / ".local").resolve()
    if not output_root.resolve().is_relative_to(local_root):
        raise AssertionError(f"{LIVE_OUTPUT_ENV} must remain beneath {local_root}.")
    return LiveConfig(
        mac_address=mac_address.upper(),
        profile_path=profile_path,
        output_root=output_root,
    )


async def _run_e2e(config: LiveConfig) -> dict[str, object]:
    profile = FtuProfile.from_json_file(config.profile_path)
    if profile.user_device_settings is None or not profile.user_device_settings.has_changes:
        raise AssertionError("Live FTU profile must declare initial user_device_settings.")

    before, data_type = await _apply_ftu_and_record(config, profile)
    store = RawRecordingStore(config.output_root)
    async with open_polar_device(config.mac_address) as device:
        offline = device.services.offline
        entry = await _wait_for_new_recording(
            offline,
            before_paths={item.path for item in before},
            data_type=data_type,
        )
        record = await offline.fetch_record(entry)
        manifest_entry = store.persist_record(config.mac_address, entry, record.payload)
        verified = store.verify_existing_record(config.mac_address, entry)
        assert manifest_entry in store.read_manifest(config.mac_address)
        cleanup = await RawRecordingCollector(
            offline,
            store,
        ).cleanup(
            config.mac_address,
            record_types={data_type.value},
            dry_run=True,
            control_client=device.services.offline_control,
        )
    managed_record = next(
        (result for result in cleanup.records if entry.path in result.deleted_paths),
        None,
    )
    return {
        "cleanup_dry_run": managed_record is not None and managed_record.status == "dry_run",
        "device_size": entry.size,
        "fetched_size": len(record.payload),
        "manifest_contains_record": manifest_entry in store.read_manifest(config.mac_address),
        "manifest_verified": verified == manifest_entry,
        "record_type": entry.record_type,
    }


async def _apply_ftu_and_record(
    config: LiveConfig, profile: FtuProfile
) -> tuple[list[object], PolarDeviceDataType]:
    async with open_polar_device(config.mac_address) as device:
        setup = device.services.setup
        await setup.do_first_time_use(profile)
        assert await setup.is_ftu_done() is True
        await setup.set_user_device_settings(profile.user_device_settings)
        _assert_settings_applied(
            profile.user_device_settings,
            await setup.get_user_device_settings(),
        )
        before = await device.services.offline.list_recording_files()
        data_type = await _record_for_smoke_window(device.services.offline_control)
    return before, data_type


async def _record_for_smoke_window(control: object) -> PolarDeviceDataType:
    available = await control.get_available_recording_types()
    status = await control.get_recording_status()
    started: PolarDeviceDataType | None = None
    try:
        for data_type in CANDIDATES:
            if data_type not in available or status.get(data_type, False):
                continue
            settings = await _minimum_start_settings(control, data_type)
            if settings is _UNAVAILABLE:
                continue
            try:
                await control.start_recording(data_type, settings)
            except PmdResponseError as exc:
                if exc.response_code in RECOVERABLE_START_RESPONSES:
                    continue
                raise
            started = data_type
            await _wait_for_active(control, data_type)
            await asyncio.sleep(SMOKE_DURATION_SECONDS)
            await control.stop_recording(data_type)
            started = None
            return data_type
        raise AssertionError("No supported inactive offline recording type could start.")
    finally:
        if started is not None:
            try:
                await control.stop_recording(started)
            except Exception:
                pass


class _Unavailable:
    pass


_UNAVAILABLE = _Unavailable()


async def _minimum_start_settings(
    control: object, data_type: PolarDeviceDataType
) -> PmdSetting | None | _Unavailable:
    if data_type in NO_SETTINGS_TYPES:
        return None
    try:
        available = await control.request_recording_settings(data_type)
    except (PmdUnsupportedOperation, PmdResponseError):
        return _UNAVAILABLE
    selected = {
        setting_type: min(values) for setting_type, values in available.settings.items() if values
    }
    return PmdSetting.from_selected(selected) if selected else _UNAVAILABLE


async def _wait_for_active(control: object, data_type: PolarDeviceDataType) -> None:
    deadline = asyncio.get_running_loop().time() + 3.0
    while True:
        if (await control.get_recording_status()).get(data_type, False):
            return
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError(f"{data_type.value} did not become active.")
        await asyncio.sleep(0.2)


async def _wait_for_new_recording(
    offline: object,
    *,
    before_paths: set[str],
    data_type: PolarDeviceDataType,
):
    deadline = asyncio.get_running_loop().time() + MATERIALIZATION_TIMEOUT_SECONDS
    while True:
        entries = await offline.list_recording_files()
        candidates = [
            entry
            for entry in entries
            if entry.path not in before_paths
            and base_record_type_for(entry.record_type) == data_type.value
        ]
        if candidates:
            return max(candidates, key=lambda entry: entry.path)
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError(f"No new {data_type.value} recording appeared after stop.")
        await asyncio.sleep(5.0)


def _assert_settings_applied(expected: object, actual: object) -> None:
    for field_name in (
        "device_location",
        "usb_connection_mode",
        "automatic_training_detection_mode",
        "automatic_training_detection_sensitivity",
        "minimum_training_duration_seconds",
        "autos_files_enabled",
    ):
        expected_value = getattr(expected, field_name)
        if expected_value is not None:
            assert getattr(actual, field_name) == expected_value
