from __future__ import annotations

import polar_ble_tools


def test_package_public_api_is_project_owned_and_has_no_generated_symbols() -> None:
    assert set(polar_ble_tools.__all__) == {
        "PmdClient",
        "DoctorReport",
        "DoctorSchemaStatus",
        "DeviceDiskSpaceResult",
        "FtuApplyResult",
        "OfflineTriggerResult",
        "PassiveDomain",
        "PolarDeviceDataType",
        "RawFetchResult",
        "RecordingCommandResult",
        "RecordingSettingsResult",
        "RecordingStatusResult",
        "RecordingTypesResult",
        "PairingError",
        "PairingStatus",
        "apply_ftu",
        "available_recording_types",
        "cleanup_raw_recordings",
        "collect_passive_files",
        "collect_raw_recordings",
        "connect_device",
        "diagnose_ftu",
        "device_disk_space",
        "discover_devices",
        "doctor",
        "fetch_raw_recording",
        "ftu_status",
        "list_raw_recordings",
        "list_passive_files",
        "pair_device",
        "offline_trigger",
        "physical_configuration",
        "release_device_connection",
        "recording_settings",
        "recording_status",
        "start_recording",
        "stop_recording",
        "update_offline_trigger",
        "update_user_device_settings",
        "user_device_settings",
        "__version__",
    }
    assert not any(
        name.startswith("Pb") or name.endswith("_pb2") for name in polar_ble_tools.__all__
    )
