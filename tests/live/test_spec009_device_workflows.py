"""Opt-in downstream device workflows for SPEC-009.

Read-only probes inspect FTU, PMD, and PFTP state. Separately gated probes
apply one explicitly selected, maintainer-approved device-specific FTU profile
or create one short ACC recording. They never pair, reset, stop an existing
recording, or delete device data.
"""

from __future__ import annotations

import asyncio
import math
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pytest

from polar_ble_tools.api import (
    apply_ftu,
    ftu_status,
    physical_configuration,
    user_device_settings,
)
from polar_ble_tools.ble.transport import BleTransport
from polar_ble_tools.device import open_polar_device
from polar_ble_tools.inventory import InventoryError, load_allowed_mac_addresses
from polar_ble_tools.polar.offline import base_record_type_for
from polar_ble_tools.polar.pmd import (
    PmdResponseCode,
    PmdResponseError,
    PmdSetting,
    PolarDeviceDataType,
)
from polar_ble_tools.polar.setup import (
    FtuProfile,
    VeritySenseFtuProfile,
    load_ftu_profile,
)
from polar_ble_tools.raw_data.collector import RawRecordingCollector
from polar_ble_tools.raw_data.storage import RawRecordingStore

SPEC009_LIVE_ENV = "POLAR_BLE_SPEC009"
SPEC009_MUTATING_ENV = "POLAR_BLE_SPEC009_MUTATING"
SPEC009_FTU_APPLY_ENV = "POLAR_BLE_SPEC009_FTU_APPLY"
SPEC009_FTU_FAMILY_ENV = "POLAR_BLE_SPEC009_FTU_FAMILY"
LIVE_MAC_ENV = "POLAR_BLE_LIVE_MAC"
LIVE_RAW_ROOT_ENV = "POLAR_BLE_LIVE_RAW_ROOT"
TEST_DEVICES_FILE = Path("test_devices.yaml")
LOOP_GEN2_FTU_PROFILE = Path("docs/loop-gen2-ftu-profile.example.json")
VERITY_SENSE_FTU_PROFILE = Path("docs/verity-sense-ftu-profile.example.json")
DEFAULT_RAW_ROOT = Path(".local/polar-ble-spec009-raw")
OPERATION_TIMEOUT_SECONDS = 60.0
SMOKE_DURATION_SECONDS = 4.0
ACTIVE_TIMEOUT_SECONDS = 3.0
MATERIALIZATION_TIMEOUT_SECONDS = 35.0
MATERIALIZATION_POLL_SECONDS = 5.0


@dataclass(frozen=True)
class Spec009WorkflowConfig:
    target: str
    raw_root: Path


def test_spec009_ftu_state_and_settings_reads() -> None:
    config = _load_config()
    result = asyncio.run(
        asyncio.wait_for(
            _read_ftu_state(config),
            timeout=OPERATION_TIMEOUT_SECONDS,
        )
    )

    assert result["ftu_done"] is True
    assert result["physical_configuration_present"] is True
    assert result["settings_field_count"] > 0
    assert result["diagnostic_field_count"] > 0
    print(
        "spec009_ftu_reads=passed "
        f"settings_fields={result['settings_field_count']} "
        f"diagnostic_fields={result['diagnostic_field_count']}"
    )


def test_spec009_pmd_and_pftp_status_reads() -> None:
    config = _load_config()
    result = asyncio.run(
        asyncio.wait_for(
            _read_pmd_and_pftp_status(config),
            timeout=OPERATION_TIMEOUT_SECONDS,
        )
    )

    assert result["available_type_count"] > 0
    assert result["status_type_count"] > 0
    assert result["trigger_mode_present"] is True
    assert result["disk_space_valid"] is True
    print(
        "spec009_pmd_pftp_reads=passed "
        f"available_types={result['available_type_count']} "
        f"status_types={result['status_type_count']}"
    )


def test_spec009_apply_loop_gen2_ftu_profile() -> None:
    config = _load_config()
    if os.environ.get(SPEC009_FTU_APPLY_ENV) != "1":
        pytest.skip(f"{SPEC009_FTU_APPLY_ENV}=1 is required.")
    if os.environ.get(SPEC009_FTU_FAMILY_ENV) != FtuProfile.device_family:
        pytest.skip(f"{SPEC009_FTU_FAMILY_ENV}={FtuProfile.device_family} is required.")
    profile = FtuProfile.from_json_file(LOOP_GEN2_FTU_PROFILE)
    verified_fields = asyncio.run(
        asyncio.wait_for(
            _apply_and_verify_loop_gen2_ftu(config, profile),
            timeout=OPERATION_TIMEOUT_SECONDS,
        )
    )

    assert verified_fields > 0
    print(f"spec009_ftu_apply=passed verified_fields={verified_fields}")


def test_spec009_apply_verity_sense_ftu_profile() -> None:
    config = _load_config()
    if os.environ.get(SPEC009_FTU_APPLY_ENV) != "1":
        pytest.skip(f"{SPEC009_FTU_APPLY_ENV}=1 is required.")
    if os.environ.get(SPEC009_FTU_FAMILY_ENV) != VeritySenseFtuProfile.device_family:
        pytest.skip(f"{SPEC009_FTU_FAMILY_ENV}={VeritySenseFtuProfile.device_family} is required.")
    profile = load_ftu_profile(VERITY_SENSE_FTU_PROFILE)
    if not isinstance(profile, VeritySenseFtuProfile):
        raise AssertionError("The documented Verity FTU profile has the wrong family.")
    verified_fields = asyncio.run(
        asyncio.wait_for(
            _apply_and_verify_verity_sense_ftu(config, profile),
            timeout=OPERATION_TIMEOUT_SECONDS,
        )
    )

    assert verified_fields == 2
    print(f"spec009_verity_ftu_apply=passed verified_fields={verified_fields}")


def test_spec009_acc_record_fetch_verify_and_cleanup_dry_run() -> None:
    config = _load_config()
    if os.environ.get(SPEC009_MUTATING_ENV) != "1":
        pytest.skip(f"{SPEC009_MUTATING_ENV}=1 is required.")
    result = asyncio.run(
        asyncio.wait_for(
            _record_fetch_verify_and_dry_run(config),
            timeout=OPERATION_TIMEOUT_SECONDS,
        )
    )

    assert result["manifest_verified"] is True
    assert result["cleanup_status"] == "dry_run"
    assert result["deleted"] == 0
    print(
        "spec009_acc_recording=passed "
        f"record_type={result['record_type']} cleanup={result['cleanup_status']}"
    )


def _load_config() -> Spec009WorkflowConfig:
    if os.environ.get(SPEC009_LIVE_ENV) != "1":
        pytest.skip(f"{SPEC009_LIVE_ENV}=1 is required.")
    target = os.environ.get(LIVE_MAC_ENV)
    if not target:
        pytest.skip(f"{LIVE_MAC_ENV} is required to select one device.")
    if not TEST_DEVICES_FILE.is_file():
        raise AssertionError(
            f"SPEC-009 live tests require a local authorized inventory: {TEST_DEVICES_FILE}"
        )
    try:
        allowed = load_allowed_mac_addresses(TEST_DEVICES_FILE)
    except InventoryError as exc:
        raise AssertionError("The SPEC-009 live-test inventory is invalid.") from exc
    normalized = target.upper()
    if normalized not in allowed:
        raise AssertionError("The SPEC-009 live-test target is not authorized.")
    raw_root = Path(os.environ.get(LIVE_RAW_ROOT_ENV, DEFAULT_RAW_ROOT))
    local_root = (Path.cwd() / ".local").resolve()
    if not raw_root.resolve().is_relative_to(local_root):
        raise AssertionError(f"{LIVE_RAW_ROOT_ENV} must remain beneath {local_root}.")
    return Spec009WorkflowConfig(target=normalized, raw_root=raw_root)


async def _read_ftu_state(config: Spec009WorkflowConfig) -> dict[str, object]:
    async with open_polar_device(config.target) as device:
        setup = device.services.setup
        ftu_done = await setup.is_ftu_done()
        physical = await setup.get_physical_configuration()
        settings = await setup.get_user_device_settings()
        diagnostics = await setup.diagnose_setup()
    return {
        "diagnostic_field_count": len(diagnostics),
        "ftu_done": ftu_done,
        "physical_configuration_present": physical is not None,
        "settings_field_count": len(settings.to_jsonable()),
    }


async def _read_pmd_and_pftp_status(
    config: Spec009WorkflowConfig,
) -> dict[str, object]:
    async with open_polar_device(config.target) as device:
        available = await device.services.offline_control.get_available_recording_types()
        status = await device.services.offline_control.get_recording_status()
        trigger = await device.services.offline_control.get_trigger_setup()
        disk_space = await device.services.pftp.get_disk_space()
        await device.services.offline.list_recording_files()
    disk_space_valid = (
        disk_space.fragment_size >= 0
        and disk_space.total_fragments >= 0
        and 0 <= disk_space.free_fragments <= disk_space.total_fragments
    )
    return {
        "available_type_count": len(available),
        "disk_space_valid": disk_space_valid,
        "status_type_count": len(status),
        "trigger_mode_present": trigger.mode is not None,
    }


async def _apply_and_verify_loop_gen2_ftu(
    config: Spec009WorkflowConfig,
    profile: FtuProfile,
) -> int:
    result = await apply_ftu(config.target, profile)
    assert result.ftu_applied is True
    assert result.settings_updated is True
    assert await ftu_status(config.target) is True

    physical = await physical_configuration(config.target)
    if physical is None:
        raise AssertionError("Physical configuration is missing after FTU application.")
    physical_expectations = {
        "gender": profile.gender,
        "birth_date": profile.birth_date,
        "max_heart_rate_bpm": profile.max_heart_rate_bpm,
        "resting_heart_rate_bpm": profile.resting_heart_rate_bpm,
        "vo2_max": profile.vo2_max,
        "training_background": profile.training_background,
        "typical_day": profile.typical_day,
        "sleep_goal_minutes": profile.sleep_goal_minutes,
    }
    for field_name, expected in physical_expectations.items():
        assert getattr(physical, field_name) == expected
    assert physical.height_cm is not None
    assert physical.weight_kg is not None
    assert math.isclose(physical.height_cm, profile.height_cm, abs_tol=0.01)
    assert math.isclose(physical.weight_kg, profile.weight_kg, abs_tol=0.01)

    patch = profile.user_device_settings
    if patch is None or not patch.has_changes:
        raise AssertionError("The Loop Gen 2 FTU profile has no settings patch.")
    settings = await user_device_settings(config.target)
    verified_settings = 0
    for field_name in (
        "device_location",
        "usb_connection_mode",
        "automatic_training_detection_mode",
        "automatic_training_detection_sensitivity",
        "minimum_training_duration_seconds",
        "autos_files_enabled",
    ):
        expected = getattr(patch, field_name)
        if expected is not None:
            assert getattr(settings, field_name) == expected
            verified_settings += 1
    return len(physical_expectations) + 2 + verified_settings


async def _apply_and_verify_verity_sense_ftu(
    config: Spec009WorkflowConfig,
    profile: VeritySenseFtuProfile,
) -> int:
    result = await apply_ftu(config.target, profile)
    assert result.ftu_applied is True
    assert result.settings_updated is True

    settings = await user_device_settings(config.target)
    assert settings.device_location is profile.device_location

    async with open_polar_device(config.target) as device:
        query_started = datetime.now().astimezone()
        device_time = await device.services.setup.get_local_time()
        query_finished = datetime.now().astimezone()
    if device_time.utcoffset() != query_started.utcoffset():
        raise AssertionError("Verity Sense timezone offset does not match the host.")
    device_utc = device_time.astimezone(timezone.utc)
    start_utc = query_started.astimezone(timezone.utc)
    finish_utc = query_finished.astimezone(timezone.utc)
    clock_interval_error = max(
        (start_utc - device_utc).total_seconds(),
        (device_utc - finish_utc).total_seconds(),
        0.0,
    )
    assert clock_interval_error <= 5.0
    return 2


async def _record_fetch_verify_and_dry_run(
    config: Spec009WorkflowConfig,
    *,
    transport_factory: Callable[[], BleTransport] | None = None,
) -> dict[str, object]:
    before_paths: set[str]
    setting: PmdSetting
    async with open_polar_device(
        config.target,
        transport_factory=transport_factory,
    ) as device:
        control = device.services.offline_control
        before_paths = {
            entry.path for entry in await device.services.offline.list_recording_files()
        }
        status = await control.get_recording_status()
        if status.get(PolarDeviceDataType.ACC, False):
            pytest.skip("ACC recording is already active; the probe will not stop it.")
        available = await control.get_available_recording_types()
        if PolarDeviceDataType.ACC not in available:
            pytest.skip("ACC offline recording is not available.")
        supported = await control.request_recording_settings(PolarDeviceDataType.ACC)
        selected = {
            setting_type: min(values)
            for setting_type, values in supported.settings.items()
            if values
        }
        if not selected:
            pytest.skip("ACC offline recording has no selectable settings.")
        setting = PmdSetting.from_selected(selected)
        started = False
        try:
            try:
                await control.start_recording(PolarDeviceDataType.ACC, setting)
            except PmdResponseError as exc:
                if exc.response_code in {
                    PmdResponseCode.ERROR_DEVICE_IN_CHARGER,
                    PmdResponseCode.ERROR_INVALID_STATE,
                }:
                    pytest.skip(
                        "ACC start is unavailable in the current device state: "
                        f"{exc.response_code.name}"
                    )
                raise
            started = True
            await _wait_for_acc_active(control)
            await asyncio.sleep(SMOKE_DURATION_SECONDS)
            await control.stop_recording(PolarDeviceDataType.ACC)
            started = False
        finally:
            if started:
                await control.stop_recording(PolarDeviceDataType.ACC)

    store = RawRecordingStore(config.raw_root)
    async with open_polar_device(
        config.target,
        transport_factory=transport_factory,
    ) as device:
        entry = await _wait_for_new_acc_recording(
            device.services.offline,
            before_paths=before_paths,
        )
        record = await device.services.offline.fetch_record(entry)
        manifest = store.persist_record(config.target, entry, record.payload)
        verified = store.verify_existing_record(config.target, entry)
        cleanup = await RawRecordingCollector(
            device.services.offline,
            store,
        ).cleanup(
            config.target,
            record_types={PolarDeviceDataType.ACC.value},
            dry_run=True,
            control_client=device.services.offline_control,
        )

    cleanup_record = next(
        (result for result in cleanup.records if entry.path in result.deleted_paths),
        None,
    )
    if cleanup_record is None:
        raise AssertionError("The new verified ACC recording was not selected by cleanup dry-run.")
    return {
        "cleanup_status": cleanup_record.status,
        "deleted": cleanup.deleted,
        "manifest_verified": verified == manifest,
        "record_type": entry.record_type,
    }


async def _wait_for_acc_active(control: object) -> None:
    deadline = asyncio.get_running_loop().time() + ACTIVE_TIMEOUT_SECONDS
    while True:
        if (await control.get_recording_status()).get(PolarDeviceDataType.ACC, False):
            return
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError("ACC recording did not become active.")
        await asyncio.sleep(0.2)


async def _wait_for_new_acc_recording(
    offline: object,
    *,
    before_paths: set[str],
):
    deadline = asyncio.get_running_loop().time() + MATERIALIZATION_TIMEOUT_SECONDS
    while True:
        entries = await offline.list_recording_files()
        candidates = [
            entry
            for entry in entries
            if entry.path not in before_paths
            and base_record_type_for(entry.record_type) == PolarDeviceDataType.ACC.value
        ]
        if candidates:
            return max(candidates, key=lambda entry: entry.path)
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError("No new ACC recording appeared after stop.")
        await asyncio.sleep(MATERIALIZATION_POLL_SECONDS)
