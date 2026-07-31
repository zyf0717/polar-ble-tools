from __future__ import annotations

import polar_ble_tools


def test_package_public_api_is_platform_neutral_and_project_owned() -> None:
    assert set(polar_ble_tools.__all__) == {
        "PmdClient",
        "DoctorReport",
        "DoctorSchemaStatus",
        "DeviceDiskSpaceResult",
        "DeviceLifecycleError",
        "DevicePlatform",
        "DiscoveredDevice",
        "FtuApplyResult",
        "LifecyclePhase",
        "LifecycleTimeouts",
        "OfflineTriggerResult",
        "PassiveDomain",
        "PolarDeviceDataType",
        "PreparationOutcome",
        "PreparationResult",
        "ProbeResult",
        "RawFetchResult",
        "ReconnectPersistence",
        "RecordingCommandResult",
        "RecordingSettingsResult",
        "RecordingStatusResult",
        "RecordingTypesResult",
        "apply_ftu",
        "available_recording_types",
        "cleanup_passive_files",
        "cleanup_raw_recordings",
        "collect_passive_files",
        "collect_raw_recordings",
        "device_disk_space",
        "diagnose_ftu",
        "doctor",
        "fetch_raw_recording",
        "ftu_status",
        "list_raw_recordings",
        "list_passive_files",
        "offline_trigger",
        "open_polar_device",
        "physical_configuration",
        "prepare_device",
        "probe_device",
        "recording_settings",
        "recording_status",
        "scan_devices",
        "start_recording",
        "stop_recording",
        "update_offline_trigger",
        "update_user_device_settings",
        "user_device_settings",
        "__version__",
    }
    removed = {
        "BluetoothDevice",
        "PairingStatus",
        "PairingError",
        "discover_devices",
        "pair_device",
        "connect_device",
        "release_device_connection",
    }
    assert removed.isdisjoint(polar_ble_tools.__all__)
    assert not any(
        name.startswith("Pb") or name.endswith("_pb2") for name in polar_ble_tools.__all__
    )
