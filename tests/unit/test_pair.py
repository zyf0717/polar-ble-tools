from pathlib import Path

from polar_ble_tools.ble.bluetoothctl_pairing import (
    BluetoothDevice,
    PairingError,
    _pairing_failure_message,
    connect_device,
    discover_devices,
    pair_device,
    parse_devices,
    parse_info,
    parse_live_scan_devices,
    release_device_connection,
    select_device,
)
from polar_ble_tools.inventory import load_allowed_mac_addresses


def test_parse_devices_deduplicates_latest_name() -> None:
    output = """
    [NEW] Device AA:BB:CC:DD:EE:FF Polar Loop Gen 2
    [CHG] Device AA:BB:CC:DD:EE:FF Polar Loop Gen 2
    [NEW] Device 11:22:33:44:55:66 Other Sensor
    """

    devices = parse_devices(output)

    assert devices == [
        BluetoothDevice(mac_address="AA:BB:CC:DD:EE:FF", name="Polar Loop Gen 2"),
        BluetoothDevice(mac_address="11:22:33:44:55:66", name="Other Sensor"),
    ]


def test_parse_devices_keeps_name_and_captures_rssi_updates() -> None:
    devices = parse_devices(
        "[NEW] Device AA:BB:CC:DD:EE:FF Polar Loop Gen 2\n"
        "[CHG] Device AA:BB:CC:DD:EE:FF RSSI: -47\n"
    )

    assert devices == [
        BluetoothDevice(
            mac_address="AA:BB:CC:DD:EE:FF",
            name="Polar Loop Gen 2",
            rssi=-47,
        )
    ]


def test_parse_live_scan_devices_excludes_cached_device_records() -> None:
    devices = parse_live_scan_devices(
        "[NEW] Device AA:BB:CC:DD:EE:FF Polar Loop Gen 2\n"
        "[CHG] Device AA:BB:CC:DD:EE:FF RSSI: -47\n"
        "Device 11:22:33:44:55:66 Cached Polar device\n"
    )

    assert devices == [
        BluetoothDevice(
            mac_address="AA:BB:CC:DD:EE:FF",
            name="Polar Loop Gen 2",
            rssi=-47,
        )
    ]


def test_select_device_requires_unique_name_match() -> None:
    devices = [
        BluetoothDevice(mac_address="AA:BB:CC:DD:EE:FF", name="Polar Loop Gen 2"),
        BluetoothDevice(mac_address="11:22:33:44:55:66", name="Polar Loop Gen 2 Backup"),
    ]

    try:
        select_device(
            devices,
            mac_address=None,
            name_substring="Polar Loop",
            allowed_mac_addresses={
                "AA:BB:CC:DD:EE:FF",
                "11:22:33:44:55:66",
            },
        )
    except PairingError as exc:
        assert "Multiple devices matched" in str(exc)
    else:
        raise AssertionError("Expected a PairingError for ambiguous device matches.")


def test_parse_info_requires_all_success_flags() -> None:
    output = """
    Device AA:BB:CC:DD:EE:FF
    \tName: Polar Loop Gen 2
    \tPaired: yes
    \tBonded: yes
    \tTrusted: yes
    \tConnected: yes
    """

    status = parse_info("AA:BB:CC:DD:EE:FF", output)

    assert status.ready is True
    assert status.mac_address == "AA:BB:CC:DD:EE:FF"


def test_connection_attempt_failure_includes_bounded_remediation() -> None:
    message = _pairing_failure_message(
        "AA:BB:CC:DD:EE:FF",
        "org.bluez.Error.ConnectionAttemptFailed",
    )

    assert "Retry once after a few seconds." in message
    assert "disconnect other hosts" in message


def test_load_allowed_mac_addresses_reads_inventory_file(tmp_path: Path) -> None:
    inventory = tmp_path / "devices.yaml"
    inventory.write_text("polar-loop-gen2:\n  - aa:bb:cc:dd:ee:ff\n", encoding="utf-8")

    allowed = load_allowed_mac_addresses(inventory)

    assert allowed == {"AA:BB:CC:DD:EE:FF"}


def test_select_device_rejects_scanned_device_outside_inventory() -> None:
    devices = [
        BluetoothDevice(mac_address="AA:BB:CC:DD:EE:FF", name="Polar Loop Gen 2"),
    ]

    try:
        select_device(
            devices,
            mac_address=None,
            name_substring="Polar Loop",
            allowed_mac_addresses={"11:22:33:44:55:66"},
        )
    except PairingError as exc:
        assert "No authorized scanned device matched" in str(exc)
    else:
        raise AssertionError("Expected a PairingError for an unauthorized scanned device.")


def test_select_device_accepts_explicit_mac_without_development_inventory() -> None:
    target = select_device(
        [BluetoothDevice(mac_address="AA:BB:CC:DD:EE:FF", name="Unknown")],
        mac_address="aa:bb:cc:dd:ee:ff",
        name_substring="Polar",
    )

    assert target.mac_address == "AA:BB:CC:DD:EE:FF"


def test_discover_devices_is_read_only_and_filters_name(monkeypatch: object) -> None:
    commands: list[str] = []

    class FakeBluetoothctlSession:
        def __init__(self, executable: str = "bluetoothctl") -> None:
            assert executable == "bluetoothctl"

        def __enter__(self) -> "FakeBluetoothctlSession":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def command(self, command: str, **_kwargs: object) -> str:
            commands.append(command)
            return ""

        def scan(self, duration_seconds: float) -> str:
            assert duration_seconds == 2.0
            return (
                "[NEW] Device AA:BB:CC:DD:EE:FF Polar Loop Gen 2\n"
                "[CHG] Device AA:BB:CC:DD:EE:FF RSSI: -47\n"
                "[NEW] Device 11:22:33:44:55:66 Other Sensor\n"
            )

    monkeypatch.setattr(
        "polar_ble_tools.ble.bluetoothctl_pairing.BluetoothctlSession",
        FakeBluetoothctlSession,
    )

    devices = discover_devices(scan_seconds=2.0, name_substring="polar")

    assert devices == [
        BluetoothDevice(
            mac_address="AA:BB:CC:DD:EE:FF",
            name="Polar Loop Gen 2",
            rssi=-47,
        )
    ]
    assert commands == ["power on"]


def test_pair_device_skips_pair_and_trust_when_already_bonded(
    monkeypatch: object,
) -> None:
    commands: list[str] = []

    class FakeBluetoothctlSession:
        def __init__(self, executable: str = "bluetoothctl") -> None:
            self.executable = executable

        def __enter__(self) -> "FakeBluetoothctlSession":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def command(
            self,
            command: str,
            *,
            idle_timeout: float = 0.4,
            total_timeout: float = 10.0,
        ) -> str:
            del idle_timeout, total_timeout
            commands.append(command)
            if command == "info AA:BB:CC:DD:EE:FF" and commands.count(command) == 1:
                return (
                    "Device AA:BB:CC:DD:EE:FF\n"
                    "\tPaired: yes\n"
                    "\tBonded: yes\n"
                    "\tTrusted: yes\n"
                    "\tConnected: no\n"
                )
            if command == "info AA:BB:CC:DD:EE:FF":
                return (
                    "Device AA:BB:CC:DD:EE:FF\n"
                    "\tPaired: yes\n"
                    "\tBonded: yes\n"
                    "\tTrusted: yes\n"
                    "\tConnected: yes\n"
                )
            return ""

        def scan(self, duration_seconds: float) -> str:
            del duration_seconds
            return "[NEW] Device AA:BB:CC:DD:EE:FF Polar Loop Gen 2\n"

    monkeypatch.setattr(
        "polar_ble_tools.ble.bluetoothctl_pairing.BluetoothctlSession",
        FakeBluetoothctlSession,
    )

    status = pair_device(
        mac_address="AA:BB:CC:DD:EE:FF",
        name_substring="Polar Loop",
        scan_seconds=0.1,
    )

    assert status.ready is True
    assert "pair AA:BB:CC:DD:EE:FF" not in commands
    assert "trust AA:BB:CC:DD:EE:FF" not in commands
    assert commands.count("connect AA:BB:CC:DD:EE:FF") == 1


def test_pair_device_accepts_bond_when_device_disconnects_after_connect(
    monkeypatch: object,
    tmp_path: Path,
) -> None:
    inventory = tmp_path / "devices.yaml"
    inventory.write_text("polar-loop-gen2:\n  - AA:BB:CC:DD:EE:FF\n", encoding="utf-8")

    class FakeBluetoothctlSession:
        def __init__(self, executable: str = "bluetoothctl") -> None:
            self.executable = executable

        def __enter__(self) -> "FakeBluetoothctlSession":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def command(
            self,
            command: str,
            *,
            idle_timeout: float = 0.4,
            total_timeout: float = 10.0,
        ) -> str:
            del command, idle_timeout, total_timeout
            return (
                "Device AA:BB:CC:DD:EE:FF\n"
                "\tPaired: yes\n"
                "\tBonded: yes\n"
                "\tTrusted: yes\n"
                "\tConnected: no\n"
            )

        def scan(self, duration_seconds: float) -> str:
            del duration_seconds
            return "[NEW] Device AA:BB:CC:DD:EE:FF Polar Loop Gen 2\n"

        def pair(self, mac_address: str, *, timeout_seconds: float = 45.0) -> str:
            del mac_address, timeout_seconds
            return "Pairing successful\n"

    monkeypatch.setattr(
        "polar_ble_tools.ble.bluetoothctl_pairing.BluetoothctlSession",
        FakeBluetoothctlSession,
    )

    status = pair_device(
        mac_address="AA:BB:CC:DD:EE:FF",
        name_substring="Polar Loop",
        scan_seconds=0.1,
        devices_file=inventory,
    )

    assert status.can_skip_pairing is True
    assert status.connected is False


def test_release_device_connection_waits_for_bluez_disconnect(
    monkeypatch: object,
    tmp_path: Path,
) -> None:
    info_calls = 0

    class FakeBluetoothctlSession:
        def __init__(self, executable: str = "bluetoothctl") -> None:
            self.executable = executable

        def __enter__(self) -> "FakeBluetoothctlSession":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def command(self, command: str, **_kwargs: object) -> str:
            nonlocal info_calls
            if command.startswith("info "):
                info_calls += 1
                connected = "yes" if info_calls == 1 else "no"
                return (
                    "Device AA:BB:CC:DD:EE:FF\n\tPaired: yes\n\tBonded: yes\n"
                    f"\tTrusted: yes\n\tConnected: {connected}\n"
                )
            return ""

    monkeypatch.setattr(
        "polar_ble_tools.ble.bluetoothctl_pairing.BluetoothctlSession",
        FakeBluetoothctlSession,
    )
    monkeypatch.setattr("polar_ble_tools.ble.bluetoothctl_pairing.time.sleep", lambda _: None)

    status = release_device_connection(
        mac_address="AA:BB:CC:DD:EE:FF",
        log_dir=tmp_path / "logs",
    )

    assert status.connected is False
    assert info_calls == 2


def test_connect_device_accepts_direct_mac_without_development_inventory(
    monkeypatch: object,
    tmp_path: Path,
) -> None:
    commands: list[str] = []

    class FakeBluetoothctlSession:
        def __init__(self, executable: str = "bluetoothctl") -> None:
            self.executable = executable

        def __enter__(self) -> "FakeBluetoothctlSession":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def command(self, command: str, **_kwargs: object) -> str:
            commands.append(command)
            connected = (
                "yes"
                if command == "info AA:BB:CC:DD:EE:FF" and commands.count(command) > 1
                else "no"
            )
            return (
                "Device AA:BB:CC:DD:EE:FF\n\tPaired: yes\n\tBonded: yes\n"
                f"\tTrusted: yes\n\tConnected: {connected}\n"
            )

    monkeypatch.setattr(
        "polar_ble_tools.ble.bluetoothctl_pairing.BluetoothctlSession",
        FakeBluetoothctlSession,
    )

    status = connect_device(
        mac_address="aa:bb:cc:dd:ee:ff",
        log_dir=tmp_path / "logs",
    )

    assert status.ready is True
    assert "connect AA:BB:CC:DD:EE:FF" in commands


def test_pair_waits_for_terminal_failure_before_trust_or_connect(
    monkeypatch: object,
    tmp_path: Path,
) -> None:
    inventory = tmp_path / "devices.yaml"
    inventory.write_text("polar-loop-gen2:\n  - AA:BB:CC:DD:EE:FF\n", encoding="utf-8")
    commands: list[str] = []

    class FakeBluetoothctlSession:
        def __init__(self, executable: str = "bluetoothctl") -> None:
            self.executable = executable

        def __enter__(self) -> "FakeBluetoothctlSession":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def command(self, command: str, **_kwargs: object) -> str:
            commands.append(command)
            if command == "info AA:BB:CC:DD:EE:FF":
                return (
                    "Device AA:BB:CC:DD:EE:FF\n"
                    "\tPaired: no\n\tBonded: no\n\tTrusted: no\n\tConnected: no\n"
                )
            return ""

        def scan(self, duration_seconds: float) -> str:
            del duration_seconds
            return "[NEW] Device AA:BB:CC:DD:EE:FF Polar Loop Gen 2\n"

        def pair(self, mac_address: str, *, timeout_seconds: float = 45.0) -> str:
            del mac_address, timeout_seconds
            raise PairingError(
                "BlueZ pairing failed for AA:BB:CC:DD:EE:FF: ConnectionAttemptFailed"
            )

    monkeypatch.setattr(
        "polar_ble_tools.ble.bluetoothctl_pairing.BluetoothctlSession",
        FakeBluetoothctlSession,
    )

    try:
        pair_device(
            mac_address="AA:BB:CC:DD:EE:FF",
            name_substring="Polar Loop",
            scan_seconds=0.1,
            devices_file=inventory,
        )
    except PairingError as exc:
        assert "ConnectionAttemptFailed" in str(exc)
    else:
        raise AssertionError("Expected PairingError.")

    assert "trust AA:BB:CC:DD:EE:FF" not in commands
    assert "connect AA:BB:CC:DD:EE:FF" not in commands
