from __future__ import annotations

import argparse
import os
import re
import selectors
import subprocess
import sys
import time
from collections.abc import Iterable
from pathlib import Path

from polar_ble_tools.ble.lifecycle import BleLifecycle, BleLifecycleEvent
from polar_ble_tools.ble.transport import BluetoothDevice, PairingStatus
from polar_ble_tools.inventory import (
    MAC_ADDRESS_RE,
    InventoryError,
    load_allowed_mac_addresses,
)
from polar_ble_tools.logging import get_hub_logger, log_event, log_status

DEVICE_LINE_RE = re.compile(
    r"^\s*(?:\[[A-Z]+\]\s+)?Device (?P<mac>(?:[0-9A-F]{2}:){5}[0-9A-F]{2}) (?P<name>.+)$",
    re.MULTILINE,
)
LIVE_DEVICE_LINE_RE = re.compile(r"^\s*\[(?:NEW|CHG)\]\s+Device .+$", re.MULTILINE)
RSSI_UPDATE_RE = re.compile(r"^RSSI:\s*(?P<rssi>-?\d+)\s*$", re.IGNORECASE)
INFO_FLAG_RE = re.compile(
    r"^\s*(?P<key>Paired|Bonded|Trusted|Connected):\s+(?P<value>yes|no)\s*$",
    re.MULTILINE,
)
PAIRING_SUCCESS_RE = re.compile(r"Pairing successful", re.IGNORECASE)
PAIRING_FAILURE_RE = re.compile(r"Failed to pair:\s*(?P<reason>.+)", re.IGNORECASE)
CONNECTION_ATTEMPT_FAILED = "org.bluez.Error.ConnectionAttemptFailed"


def _pairing_failure_message(mac_address: str, reason: str) -> str:
    message = f"BlueZ pairing failed for {mac_address}: {reason}"
    if CONNECTION_ATTEMPT_FAILED not in reason:
        return message
    return (
        f"{message}\n"
        "Retry once after a few seconds. If it persists, disconnect other hosts and check BlueZ logs."
    )


class PairingError(RuntimeError):
    """Raised when BLE pairing cannot be completed."""


def _load_allowed_or_pairing_error(path: str | Path) -> set[str]:
    try:
        return load_allowed_mac_addresses(path)
    except InventoryError as exc:
        raise PairingError(str(exc)) from exc


def _log_lifecycle(
    lifecycle: BleLifecycle | None,
    event: BleLifecycleEvent,
    *,
    logger: object | None = None,
    detail: str | None = None,
) -> None:
    if lifecycle is None:
        return
    snapshot = lifecycle.transition(event, detail=detail)
    if logger is not None:
        log_event(
            logger,  # type: ignore[arg-type]
            "ble_lifecycle",
            lifecycle_event=snapshot.event.value if snapshot.event else None,
            state=snapshot.state.value,
            previous_state=snapshot.previous_state.value if snapshot.previous_state else None,
            detail=snapshot.detail,
        )


def _log_connection_result(
    lifecycle: BleLifecycle | None,
    status: PairingStatus,
    *,
    logger: object | None = None,
) -> None:
    if status.connected:
        _log_lifecycle(lifecycle, BleLifecycleEvent.CONNECTED, logger=logger)
        return
    _log_lifecycle(
        lifecycle,
        BleLifecycleEvent.DISCONNECTED,
        logger=logger,
        detail="connect not held",
    )


def parse_devices(output: str) -> list[BluetoothDevice]:
    devices: dict[str, BluetoothDevice] = {}
    for match in DEVICE_LINE_RE.finditer(output):
        mac_address = match.group("mac").upper()
        detail = match.group("name").strip()
        previous = devices.get(mac_address)
        rssi_match = RSSI_UPDATE_RE.fullmatch(detail)
        if rssi_match is not None:
            devices[mac_address] = BluetoothDevice(
                mac_address=mac_address,
                name=previous.name if previous else "",
                rssi=int(rssi_match.group("rssi")),
            )
            continue
        devices[mac_address] = BluetoothDevice(
            mac_address=mac_address,
            name=detail,
            rssi=previous.rssi if previous else None,
        )
    return list(devices.values())


def parse_live_scan_devices(output: str) -> list[BluetoothDevice]:
    """Parse only device observations emitted while ``bluetoothctl`` scans."""
    return parse_devices("\n".join(LIVE_DEVICE_LINE_RE.findall(output)))


def select_device(
    devices: Iterable[BluetoothDevice],
    *,
    mac_address: str | None,
    name_substring: str,
    allowed_mac_addresses: set[str] | None = None,
) -> BluetoothDevice:
    device_list = list(devices)
    if allowed_mac_addresses is not None:
        device_list = [
            device for device in device_list if device.mac_address.upper() in allowed_mac_addresses
        ]
    if mac_address:
        target = mac_address.upper()
        if allowed_mac_addresses is not None and target not in allowed_mac_addresses:
            raise PairingError(f"Target device {target} is not authorized in devices.yaml.")
        for device in device_list:
            if device.mac_address == target:
                return device
        raise PairingError(f"Target device {target} is authorized but was not found during scan.")

    matches = [
        device for device in device_list if name_substring.casefold() in device.name.casefold()
    ]
    if not matches:
        raise PairingError(f"No authorized scanned device matched name filter {name_substring!r}.")
    if len(matches) > 1:
        rendered = ", ".join(f"{device.name} [{device.mac_address}]" for device in matches)
        raise PairingError(
            "Multiple devices matched the requested name filter: "
            f"{rendered}. Re-run with --mac-address."
        )
    return matches[0]


def discover_devices(
    *,
    scan_seconds: float = 10.0,
    name_substring: str | None = None,
    executable: str = "bluetoothctl",
) -> list[BluetoothDevice]:
    """Read nearby BLE advertisements without pairing or connecting.

    ``bluetoothctl`` owns the BlueZ scan, so the resulting MAC addresses can be
    passed directly to :func:`pair_device` without a second scanner backend.
    """
    if scan_seconds <= 0:
        raise ValueError("scan_seconds must be greater than zero.")
    with BluetoothctlSession(executable=executable) as session:
        session.command("power on")
        devices = _scan_discovered_devices(session, scan_seconds)
    if name_substring is None:
        return devices
    return [device for device in devices if name_substring.casefold() in device.name.casefold()]


def parse_info(mac_address: str, output: str) -> PairingStatus:
    flags = {
        match.group("key").lower(): match.group("value") == "yes"
        for match in INFO_FLAG_RE.finditer(output)
    }
    missing = {"paired", "bonded", "trusted", "connected"} - flags.keys()
    if missing:
        missing_text = ", ".join(sorted(missing))
        raise PairingError(
            f"Device info for {mac_address} is incomplete; missing {missing_text}.\n{output}"
        )
    return PairingStatus(
        mac_address=mac_address.upper(),
        paired=flags["paired"],
        bonded=flags["bonded"],
        trusted=flags["trusted"],
        connected=flags["connected"],
        raw_info=output,
    )


def parse_info_or_none(mac_address: str, output: str) -> PairingStatus | None:
    try:
        return parse_info(mac_address, output)
    except PairingError:
        return None


class BluetoothctlSession:
    def __init__(self, executable: str = "bluetoothctl") -> None:
        self.executable = executable
        self._process: subprocess.Popen[str] | None = None
        self._selector: selectors.BaseSelector | None = None

    def __enter__(self) -> BluetoothctlSession:
        self._process = subprocess.Popen(
            [self.executable],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        if self._process.stdout is None:
            raise PairingError("bluetoothctl did not expose stdout.")
        os.set_blocking(self._process.stdout.fileno(), False)
        self._selector = selectors.DefaultSelector()
        self._selector.register(self._process.stdout, selectors.EVENT_READ)
        self._read_until_quiet(idle_timeout=0.2, total_timeout=0.5)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if self._process and self._process.poll() is None:
                self.command("exit", idle_timeout=0.2, total_timeout=1.0)
        finally:
            if self._selector is not None:
                self._selector.close()
            if self._process is not None:
                self._process.wait(timeout=2)

    def command(
        self,
        command: str,
        *,
        idle_timeout: float = 0.4,
        total_timeout: float = 10.0,
    ) -> str:
        if self._process is None or self._process.stdin is None:
            raise PairingError("bluetoothctl session is not active.")
        if self._process.poll() is not None:
            raise PairingError("bluetoothctl exited before the command could be sent.")
        self._process.stdin.write(command + "\n")
        self._process.stdin.flush()
        return self._read_until_quiet(
            idle_timeout=idle_timeout,
            total_timeout=total_timeout,
        )

    def scan(self, duration_seconds: float) -> str:
        collected = [self.command("scan le", idle_timeout=0.8, total_timeout=2.0)]
        deadline = time.monotonic() + duration_seconds
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            collected.append(
                self._read_until_quiet(
                    idle_timeout=min(0.5, max(remaining, 0.1)),
                    total_timeout=min(1.0, max(remaining, 0.1)),
                )
            )
        collected.append(self.command("scan off", idle_timeout=0.8, total_timeout=5.0))
        return "".join(collected)

    def pair(self, mac_address: str, *, timeout_seconds: float = 45.0) -> str:
        """Wait for BlueZ to report a terminal pairing result.

        ``bluetoothctl pair`` returns immediately after starting the connection;
        advancing to trust/connect at that point races the bonding exchange.
        """
        output = self.command(
            f"pair {mac_address}",
            idle_timeout=0.2,
            total_timeout=2.0,
        )
        deadline = time.monotonic() + timeout_seconds
        while True:
            failure = PAIRING_FAILURE_RE.search(output)
            if failure:
                raise PairingError(
                    _pairing_failure_message(mac_address, failure.group("reason").strip())
                )
            if PAIRING_SUCCESS_RE.search(output):
                return output
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise PairingError(f"Timed out waiting for BlueZ pairing result for {mac_address}.")
            output += self._read_until_quiet(
                idle_timeout=min(0.5, remaining),
                total_timeout=min(1.0, remaining),
            )

    def _read_until_quiet(self, *, idle_timeout: float, total_timeout: float) -> str:
        if self._process is None or self._process.stdout is None or self._selector is None:
            raise PairingError("bluetoothctl session is not active.")

        chunks: list[str] = []
        deadline = time.monotonic() + total_timeout
        last_activity = time.monotonic()

        while time.monotonic() < deadline:
            timeout = min(idle_timeout, max(deadline - time.monotonic(), 0.0))
            events = self._selector.select(timeout)
            if not events:
                if chunks and time.monotonic() - last_activity >= idle_timeout:
                    break
                continue
            for key, _ in events:
                try:
                    chunk = os.read(key.fileobj.fileno(), 4096)
                except BlockingIOError:
                    continue
                if chunk == b"":
                    if self._process.poll() is not None:
                        return "".join(chunks)
                    continue
                chunks.append(chunk.decode(errors="replace"))
                last_activity = time.monotonic()
        return "".join(chunks)


def _scan_discovered_devices(
    session: BluetoothctlSession,
    scan_seconds: float,
) -> list[BluetoothDevice]:
    """Use the shared BlueZ discovery path for discovery and pairing."""
    return parse_live_scan_devices(session.scan(scan_seconds))


def pair_device(
    *,
    mac_address: str | None,
    name_substring: str = "Polar",
    scan_seconds: float = 10.0,
    devices_file: str | Path | None = None,
    log_dir: str | Path = "logs",
    executable: str = "bluetoothctl",
    lifecycle: BleLifecycle | None = None,
) -> PairingStatus:
    """Discover and pair one device, returning its resulting BlueZ state.

    Supply ``mac_address`` for deterministic pairing. ``name_substring`` is
    only used when selecting a unique discovered device without a MAC address.
    """
    if mac_address and not MAC_ADDRESS_RE.fullmatch(mac_address):
        raise PairingError(f"Invalid MAC address: {mac_address}")
    if scan_seconds <= 0:
        raise PairingError("scan_seconds must be greater than zero.")
    allowed_mac_addresses = (
        _load_allowed_or_pairing_error(devices_file) if devices_file is not None else None
    )
    logger = get_hub_logger("pair", log_dir)

    try:
        with BluetoothctlSession(executable=executable) as session:
            session.command("power on")
            session.command("agent on")
            session.command("default-agent")
            _log_lifecycle(lifecycle, BleLifecycleEvent.START_SCAN, logger=logger)
            devices = _scan_discovered_devices(session, scan_seconds)
            device = select_device(
                devices,
                mac_address=mac_address,
                name_substring=name_substring,
                allowed_mac_addresses=allowed_mac_addresses,
            )
            log_event(logger, "selected_device", mac=device.mac_address, name=device.name)
            existing_info_output = session.command(
                f"info {device.mac_address}",
                idle_timeout=0.8,
                total_timeout=10.0,
            )
            existing_status = parse_info_or_none(device.mac_address, existing_info_output)
            if existing_status:
                log_status(logger, "pre_pair_check", existing_status)
            else:
                log_event(logger, "pre_pair_check_unavailable", mac=device.mac_address)
            if existing_status and existing_status.can_skip_pairing:
                _log_lifecycle(
                    lifecycle,
                    BleLifecycleEvent.START_PAIRING,
                    logger=logger,
                    detail="already bonded",
                )
                _log_lifecycle(
                    lifecycle,
                    BleLifecycleEvent.PAIRING_COMPLETE,
                    logger=logger,
                    detail="already bonded",
                )
                if existing_status.connected:
                    status = existing_status
                    _log_lifecycle(lifecycle, BleLifecycleEvent.CONNECTED, logger=logger)
                else:
                    log_event(logger, "connect_only", mac=device.mac_address)
                    _log_lifecycle(lifecycle, BleLifecycleEvent.START_CONNECT, logger=logger)
                    session.command(
                        f"connect {device.mac_address}",
                        idle_timeout=1.0,
                        total_timeout=30.0,
                    )
                    info_output = session.command(
                        f"info {device.mac_address}",
                        idle_timeout=0.8,
                        total_timeout=10.0,
                    )
                    status = parse_info(device.mac_address, info_output)
                    _log_connection_result(lifecycle, status, logger=logger)
            else:
                log_event(logger, "pair_sequence_start", mac=device.mac_address)
                _log_lifecycle(lifecycle, BleLifecycleEvent.START_PAIRING, logger=logger)
                session.pair(device.mac_address)
                session.command(
                    f"trust {device.mac_address}",
                    idle_timeout=0.8,
                    total_timeout=10.0,
                )
                _log_lifecycle(
                    lifecycle,
                    BleLifecycleEvent.PAIRING_COMPLETE,
                    logger=logger,
                )
                _log_lifecycle(lifecycle, BleLifecycleEvent.START_CONNECT, logger=logger)
                session.command(
                    f"connect {device.mac_address}",
                    idle_timeout=1.0,
                    total_timeout=30.0,
                )
                info_output = session.command(
                    f"info {device.mac_address}",
                    idle_timeout=0.8,
                    total_timeout=10.0,
                )
                status = parse_info(device.mac_address, info_output)
                _log_connection_result(lifecycle, status, logger=logger)
    except Exception as exc:
        lifecycle.fail(str(exc)) if lifecycle is not None else None
        raise

    if not status.can_skip_pairing:
        log_status(logger, "pair_invalid_final_state", status)
        raise PairingError(
            f"Pairing completed with an invalid final state for {device.mac_address}.\n"
            f"{status.raw_info}"
        )
    log_status(logger, "pair_complete", status)
    return status


def resolve_target_mac_address(
    mac_address: str | None,
    allowed_mac_addresses: set[str] | None = None,
) -> str:
    if mac_address:
        target = mac_address.upper()
        if not MAC_ADDRESS_RE.fullmatch(target):
            raise PairingError(f"Invalid MAC address: {mac_address}")
        if allowed_mac_addresses is not None and target not in allowed_mac_addresses:
            raise PairingError(f"Target device {target} is not authorized in devices.yaml.")
        return target
    if allowed_mac_addresses is None:
        raise PairingError("--mac-address is required when no development inventory is supplied.")
    if len(allowed_mac_addresses) != 1:
        rendered = ", ".join(sorted(allowed_mac_addresses))
        raise PairingError(
            "Multiple authorized devices are configured. Re-run with --mac-address. "
            f"Authorized devices: {rendered}"
        )
    return next(iter(allowed_mac_addresses))


def connect_device(
    *,
    mac_address: str | None = None,
    devices_file: str | Path | None = None,
    log_dir: str | Path = "logs",
    executable: str = "bluetoothctl",
    lifecycle: BleLifecycle | None = None,
) -> PairingStatus:
    """Connect an existing BlueZ bond and return its resulting state."""
    allowed_mac_addresses = (
        _load_allowed_or_pairing_error(devices_file) if devices_file is not None else None
    )
    target_mac_address = resolve_target_mac_address(mac_address, allowed_mac_addresses)
    logger = get_hub_logger("connect", log_dir)
    log_event(logger, "connect_start", mac=target_mac_address)

    try:
        with BluetoothctlSession(executable=executable) as session:
            session.command("power on")
            existing_info_output = session.command(
                f"info {target_mac_address}",
                idle_timeout=0.8,
                total_timeout=10.0,
            )
            existing_status = parse_info_or_none(target_mac_address, existing_info_output)
            if existing_status is None:
                log_event(logger, "connect_precheck_unavailable", mac=target_mac_address)
                raise PairingError(
                    f"Device {target_mac_address} is not known to BlueZ. Pair it first."
                )
            log_status(logger, "connect_precheck", existing_status)
            if not existing_status.can_skip_pairing:
                raise PairingError(
                    f"Device {target_mac_address} is not fully paired, bonded, and trusted. "
                    "Run pair.py first."
                )
            _log_lifecycle(lifecycle, BleLifecycleEvent.START_CONNECT, logger=logger)
            if existing_status.connected:
                log_status(logger, "connect_already_connected", existing_status)
                _log_lifecycle(lifecycle, BleLifecycleEvent.CONNECTED, logger=logger)
                return existing_status

            log_event(logger, "connect_attempt", mac=target_mac_address)
            session.command(
                f"connect {target_mac_address}",
                idle_timeout=1.0,
                total_timeout=30.0,
            )
            info_output = session.command(
                f"info {target_mac_address}",
                idle_timeout=0.8,
                total_timeout=10.0,
            )
            status = parse_info(target_mac_address, info_output)
            _log_connection_result(lifecycle, status, logger=logger)
    except Exception as exc:
        lifecycle.fail(str(exc)) if lifecycle is not None else None
        raise

    if not status.ready:
        log_status(logger, "connect_invalid_final_state", status)
        raise PairingError(
            f"Connection completed with an invalid final state for {target_mac_address}.\n"
            f"{status.raw_info}"
        )
    log_status(logger, "connect_complete", status)
    return status


def release_device_connection(
    *,
    mac_address: str,
    devices_file: str | Path | None = None,
    log_dir: str | Path = "logs",
    executable: str = "bluetoothctl",
    timeout_seconds: float = 15.0,
) -> PairingStatus:
    """Release a BlueZ connection while preserving the bond.

    Pairing intentionally makes a best-effort connection. Call this before a
    separate Bleak client takes ownership of the same peripheral.
    """
    allowed = _load_allowed_or_pairing_error(devices_file) if devices_file is not None else None
    target = resolve_target_mac_address(mac_address, allowed)
    logger = get_hub_logger("disconnect", log_dir)
    deadline = time.monotonic() + timeout_seconds
    with BluetoothctlSession(executable=executable) as session:
        session.command("power on")
        session.command(f"disconnect {target}", idle_timeout=0.8, total_timeout=timeout_seconds)
        while True:
            status = parse_info(
                target,
                session.command(f"info {target}", idle_timeout=0.8, total_timeout=10.0),
            )
            if not status.connected:
                break
            if time.monotonic() >= deadline:
                raise PairingError("BlueZ did not release the device connection.")
            time.sleep(0.5)
    if not status.can_skip_pairing:
        raise PairingError("BlueZ release changed the device pairing state unexpectedly.")
    log_status(logger, "disconnect_complete", status)
    return status


def build_pair_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Pair, bond, trust, and best-effort connect a Polar BLE device via BlueZ bluetoothctl."
        )
    )
    parser.add_argument(
        "--mac-address",
        help="Target device MAC address. If omitted, the first unique name match is used.",
    )
    parser.add_argument(
        "--name",
        default="Polar Loop",
        help="Case-insensitive device name substring used during scan. Default: %(default)s",
    )
    parser.add_argument(
        "--scan-seconds",
        type=float,
        default=10.0,
        help="Duration of the BLE scan before pairing. Default: %(default)s",
    )
    parser.add_argument(
        "--bluetoothctl",
        default="bluetoothctl",
        help="Path to the bluetoothctl executable. Default: %(default)s",
    )
    parser.add_argument(
        "--devices-file",
        help="Optional development YAML inventory used to restrict target selection.",
    )
    parser.add_argument(
        "--log-dir",
        default="logs",
        help="Directory for pairing state logs. Default: %(default)s",
    )
    return parser


def build_connect_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Connect a paired Polar BLE device via BlueZ bluetoothctl."
    )
    parser.add_argument(
        "--mac-address",
        help="Target device MAC address. Required unless a development inventory has one entry.",
    )
    parser.add_argument(
        "--bluetoothctl",
        default="bluetoothctl",
        help="Path to the bluetoothctl executable. Default: %(default)s",
    )
    parser.add_argument(
        "--devices-file",
        help="Optional development YAML inventory used to restrict target selection.",
    )
    parser.add_argument(
        "--log-dir",
        default="logs",
        help="Directory for connection state logs. Default: %(default)s",
    )
    return parser


def pair_main(argv: list[str] | None = None) -> int:
    parser = build_pair_parser()
    args = parser.parse_args(argv)
    try:
        status = pair_device(
            mac_address=args.mac_address,
            name_substring=args.name,
            scan_seconds=args.scan_seconds,
            devices_file=args.devices_file,
            log_dir=args.log_dir,
            executable=args.bluetoothctl,
            lifecycle=BleLifecycle(),
        )
    except FileNotFoundError as exc:
        print(f"bluetoothctl is not installed or not on PATH: {exc}", file=sys.stderr)
        return 1
    except PairingError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(f"Paired {status.mac_address}")
    print(f"Paired: {'yes' if status.paired else 'no'}")
    print(f"Bonded: {'yes' if status.bonded else 'no'}")
    print(f"Trusted: {'yes' if status.trusted else 'no'}")
    print(f"Connected: {'yes' if status.connected else 'no'}")
    return 0


def connect_main(argv: list[str] | None = None) -> int:
    parser = build_connect_parser()
    args = parser.parse_args(argv)
    try:
        status = connect_device(
            mac_address=args.mac_address,
            devices_file=args.devices_file,
            log_dir=args.log_dir,
            executable=args.bluetoothctl,
            lifecycle=BleLifecycle(),
        )
    except FileNotFoundError as exc:
        print(f"bluetoothctl is not installed or not on PATH: {exc}", file=sys.stderr)
        return 1
    except PairingError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(f"Connected {status.mac_address}")
    print("Paired: yes")
    print("Bonded: yes")
    print("Trusted: yes")
    print("Connected: yes")
    return 0
