from __future__ import annotations

import polar_ble_tools


def test_package_public_api_is_project_owned_and_has_no_generated_symbols() -> None:
    assert set(polar_ble_tools.__all__) == {
        "PmdClient",
        "PolarDeviceDataType",
        "PairingError",
        "PairingStatus",
        "cleanup_raw_recordings",
        "collect_raw_recordings",
        "connect_device",
        "discover_devices",
        "list_raw_recordings",
        "pair_device",
        "release_device_connection",
        "__version__",
    }
    assert not any(
        name.startswith("Pb") or name.endswith("_pb2") for name in polar_ble_tools.__all__
    )
