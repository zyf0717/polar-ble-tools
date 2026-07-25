"""Unofficial local BLE tooling for supported Polar devices."""

from polar_ble_tools.ble.bluetoothctl_pairing import (
    PairingError,
    connect_device,
    discover_devices,
    pair_device,
    release_device_connection,
)
from polar_ble_tools.ble.transport import PairingStatus
from polar_ble_tools.collection import (
    cleanup_raw_recordings,
    collect_raw_recordings,
    list_raw_recordings,
)
from polar_ble_tools.polar.pmd import PmdClient, PolarDeviceDataType

__all__ = [
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
]

__version__ = "0.1.0"
