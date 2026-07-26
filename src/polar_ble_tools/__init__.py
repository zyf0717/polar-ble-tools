"""Unofficial local BLE tooling for supported Polar devices."""

from importlib.metadata import version

from polar_ble_tools.api import (
    DoctorReport,
    DoctorSchemaStatus,
    FtuApplyResult,
    apply_ftu,
    diagnose_ftu,
    doctor,
    ftu_status,
    physical_configuration,
    update_user_device_settings,
    user_device_settings,
)
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
    collect_passive_files,
    collect_raw_recordings,
    list_passive_files,
    list_raw_recordings,
)
from polar_ble_tools.polar.passive import PassiveDomain
from polar_ble_tools.polar.pmd import PmdClient, PolarDeviceDataType

__all__ = [
    "PmdClient",
    "DoctorReport",
    "DoctorSchemaStatus",
    "FtuApplyResult",
    "PassiveDomain",
    "PolarDeviceDataType",
    "PairingError",
    "PairingStatus",
    "apply_ftu",
    "cleanup_raw_recordings",
    "collect_passive_files",
    "collect_raw_recordings",
    "connect_device",
    "diagnose_ftu",
    "discover_devices",
    "doctor",
    "ftu_status",
    "list_raw_recordings",
    "list_passive_files",
    "pair_device",
    "physical_configuration",
    "release_device_connection",
    "update_user_device_settings",
    "user_device_settings",
    "__version__",
]

__version__ = version("polar-ble-tools")
