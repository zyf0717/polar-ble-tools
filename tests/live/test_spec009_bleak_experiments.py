"""Opt-in Bleak experiments for SPEC-009.

The default probes require an already prepared device in the ignored private
inventory. Fresh preparation is separately gated and assumes the maintainer
has reset the device, removed its exact host-side bond, and, on Linux,
registered an appropriate BlueZ authentication agent. These probes never remove
a bond, write device settings, control recordings, fetch payloads, or delete
device data.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest
from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice

from polar_ble_tools.ble.bleak_backend import BleakSession
from polar_ble_tools.inventory import InventoryError, load_allowed_identifiers
from polar_ble_tools.polar.offline import OfflineRecordingControlClient
from polar_ble_tools.polar.pftp import PftpClient
from polar_ble_tools.polar.pmd import PmdClient
from polar_ble_tools.polar.uuids import PFTP_SERVICE, PMD_SERVICE

SPEC009_LIVE_ENV = "POLAR_BLE_SPEC009"
SPEC009_FRESH_PREPARATION_ENV = "POLAR_BLE_SPEC009_FRESH_PREPARATION"
LIVE_MAC_ENV = "POLAR_BLE_LIVE_MAC"
LIVE_SECONDARY_MAC_ENV = "POLAR_BLE_LIVE_SECONDARY_MAC"
TEST_DEVICES_FILE = Path("test_devices.yaml")
DISCOVERY_TIMEOUT_SECONDS = 10.0
CONNECT_TIMEOUT_SECONDS = 20.0
PAIRING_TIMEOUT_SECONDS = 45.0
TEST_TIMEOUT_SECONDS = 60.0
FRESH_PREPARATION_TEST_TIMEOUT_SECONDS = 90.0
TWO_DEVICE_TEST_TIMEOUT_SECONDS = 120.0
REPEAT_CONNECTIONS = 3
MISSING_DEVICE_ADDRESS = "00:00:00:00:00:00"


def test_spec009_fresh_bleak_preparation() -> None:
    target = _load_authorized_target()
    if os.environ.get(SPEC009_FRESH_PREPARATION_ENV) != "1":
        pytest.skip(f"{SPEC009_FRESH_PREPARATION_ENV}=1 is required.")
    result = asyncio.run(
        asyncio.wait_for(
            _fresh_bleak_preparation(target),
            timeout=FRESH_PREPARATION_TEST_TIMEOUT_SECONDS,
        )
    )

    assert result["initial_connection_ready"] is True
    assert result["initial_final_connected"] is False
    assert result["reconnect_ready"] is True
    assert result["reconnect_final_connected"] is False
    print("spec009_fresh_bleak_preparation=passed connections=2")


def test_spec009_structured_discovery_and_native_reconnect() -> None:
    target = _load_authorized_target()
    result = asyncio.run(
        asyncio.wait_for(
            _structured_discovery_and_native_reconnect(target),
            timeout=TEST_TIMEOUT_SECONDS,
        )
    )

    assert result["local_name_present"] is True
    assert result["rssi_present"] is True
    assert result["service_uuid_count"] > 0
    assert result["completed_connections"] == REPEAT_CONNECTIONS
    print(
        "spec009_native_reconnect=passed "
        f"connections={result['completed_connections']} "
        f"advertised_services={result['service_uuid_count']}"
    )


def test_spec009_cancellation_cleanup_and_recovery() -> None:
    target = _load_authorized_target()
    result = asyncio.run(
        asyncio.wait_for(
            _cancellation_cleanup_and_recovery(target),
            timeout=TEST_TIMEOUT_SECONDS,
        )
    )

    assert result["scanner_cancelled"] is True
    assert result["connected_after_cleanup"] is False
    assert result["recovery_connected"] is True
    assert result["recovery_final_connected"] is False
    print(
        "spec009_cancellation_recovery=passed "
        f"connect_cancelled={str(result['connect_cancelled']).lower()}"
    )


def test_spec009_shared_scan_two_device_concurrency() -> None:
    first, second = _load_authorized_pair()
    result = asyncio.run(
        asyncio.wait_for(
            _shared_scan_two_device_concurrency(first, second),
            timeout=TWO_DEVICE_TEST_TIMEOUT_SECONDS,
        )
    )

    assert result["observed_devices"] == 2
    assert result["completed_cycles"] == REPEAT_CONNECTIONS
    assert result["concurrent_connections_per_cycle"] == 2
    assert result["all_pmd_reads_passed"] is True
    assert result["all_pftp_reads_passed"] is True
    assert result["all_disconnected"] is True
    print(
        "spec009_two_device_concurrency=passed "
        f"devices={result['observed_devices']} cycles={result['completed_cycles']}"
    )


def test_spec009_two_device_connect_cancellation_and_recovery() -> None:
    first, second = _load_authorized_pair()
    result = asyncio.run(
        asyncio.wait_for(
            _two_device_connect_cancellation_and_recovery(first, second),
            timeout=TWO_DEVICE_TEST_TIMEOUT_SECONDS,
        )
    )

    assert result == {
        "cancelled": True,
        "cleanup_disconnected": True,
        "recovery_disconnected": True,
        "recovery_pftp_ready": True,
        "recovery_pmd_ready": True,
        "survivor_ready": True,
    }
    print("spec009_two_device_cancellation=passed survivor_ready=true cleanup=true recovery=true")


def _load_authorized_target() -> str:
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
        allowed = load_allowed_identifiers(TEST_DEVICES_FILE)
    except InventoryError as exc:
        raise AssertionError("The SPEC-009 live-test inventory is invalid.") from exc
    normalized = target.upper()
    if normalized not in allowed:
        raise AssertionError("The SPEC-009 live-test target is not authorized.")
    return normalized


def _load_authorized_pair() -> tuple[str, str]:
    first = _load_authorized_target()
    second = os.environ.get(LIVE_SECONDARY_MAC_ENV)
    if not second:
        pytest.skip(f"{LIVE_SECONDARY_MAC_ENV} is required for the multi-device probe.")
    try:
        allowed = load_allowed_identifiers(TEST_DEVICES_FILE)
    except InventoryError as exc:
        raise AssertionError("The SPEC-009 live-test inventory is invalid.") from exc
    normalized_second = second.upper()
    if normalized_second not in allowed:
        raise AssertionError("The secondary SPEC-009 live-test target is not authorized.")
    if normalized_second == first:
        raise AssertionError(f"{LIVE_SECONDARY_MAC_ENV} must differ from {LIVE_MAC_ENV}.")
    return first, normalized_second


async def _structured_discovery_and_native_reconnect(target: str) -> dict[str, object]:
    observations = await BleakScanner.discover(
        timeout=DISCOVERY_TIMEOUT_SECONDS,
        return_adv=True,
    )
    match = next(
        (
            (device, advertisement)
            for device, advertisement in observations.values()
            if device.address.casefold() == target.casefold()
        ),
        None,
    )
    if match is None:
        raise AssertionError("The authorized SPEC-009 target was not observed.")
    _device, advertisement = match

    completed = 0
    for _attempt in range(REPEAT_CONNECTIONS):
        device = await BleakScanner.find_device_by_address(
            target,
            timeout=DISCOVERY_TIMEOUT_SECONDS,
        )
        if device is None:
            raise AssertionError("The authorized SPEC-009 target was not resolved.")
        client = BleakClient(device, pair=False, timeout=CONNECT_TIMEOUT_SECONDS)
        try:
            await client.connect()
            _assert_required_services(client)
            completed += 1
        finally:
            await client.disconnect()
        assert client.is_connected is False

    return {
        "completed_connections": completed,
        "local_name_present": bool(advertisement.local_name),
        "rssi_present": isinstance(advertisement.rssi, int),
        "service_uuid_count": len(advertisement.service_uuids),
    }


async def _shared_scan_two_device_concurrency(
    first: str,
    second: str,
) -> dict[str, object]:
    devices = await _discover_authorized_pair(first, second)
    observed_devices = len(devices)
    targets = {device.address.casefold(): device for device in devices}
    pmd_reads_passed = 0
    pftp_reads_passed = 0
    all_disconnected = True
    for _attempt in range(REPEAT_CONNECTIONS):
        clients = [
            BleakClient(targets[target], pair=False, timeout=CONNECT_TIMEOUT_SECONDS)
            for target in sorted(targets)
        ]
        try:
            await asyncio.gather(*(client.connect() for client in clients))
            if not all(client.is_connected for client in clients):
                raise AssertionError("Both native clients were not connected concurrently.")
            results = await asyncio.gather(
                *(_read_only_native_client_workflow(client) for client in clients)
            )
            pmd_reads_passed += sum(type_count > 0 for type_count, _disk_valid in results)
            pftp_reads_passed += sum(disk_valid for _type_count, disk_valid in results)
        finally:
            await asyncio.gather(
                *(client.disconnect() for client in clients),
                return_exceptions=True,
            )
        all_disconnected = all_disconnected and all(
            client.is_connected is False for client in clients
        )

    expected_reads = REPEAT_CONNECTIONS * observed_devices
    return {
        "all_disconnected": all_disconnected,
        "all_pftp_reads_passed": pftp_reads_passed == expected_reads,
        "all_pmd_reads_passed": pmd_reads_passed == expected_reads,
        "completed_cycles": REPEAT_CONNECTIONS,
        "concurrent_connections_per_cycle": observed_devices,
        "observed_devices": observed_devices,
    }


async def _discover_authorized_pair(first: str, second: str) -> list[BLEDevice]:
    targets = {first.casefold(), second.casefold()}
    observations = await BleakScanner.discover(
        timeout=DISCOVERY_TIMEOUT_SECONDS,
        return_adv=True,
    )
    devices = {
        device.address.casefold(): device
        for device, _advertisement in observations.values()
        if device.address.casefold() in targets
    }
    if set(devices) != targets:
        raise AssertionError("Both authorized SPEC-009 targets were not observed.")
    return [devices[target] for target in sorted(targets)]


async def _read_only_native_client_workflow(client: BleakClient) -> tuple[int, bool]:
    _assert_required_services(client)
    session = BleakSession(client)
    available, disk_space = await asyncio.gather(
        OfflineRecordingControlClient(PmdClient(session)).get_available_recording_types(),
        PftpClient(session).get_disk_space(),
    )
    disk_valid = 0 <= disk_space.free_fragments <= disk_space.total_fragments
    return len(available), disk_valid


async def _two_device_connect_cancellation_and_recovery(
    first: str,
    second: str,
) -> dict[str, bool]:
    devices = await _discover_authorized_pair(first, second)
    clients = [
        BleakClient(device, pair=False, timeout=CONNECT_TIMEOUT_SECONDS) for device in devices
    ]
    connect_tasks = [asyncio.create_task(client.connect()) for client in clients]
    await asyncio.sleep(0.25)
    connect_tasks[0].cancel()
    connect_results = await asyncio.gather(*connect_tasks, return_exceptions=True)
    cancelled = isinstance(connect_results[0], asyncio.CancelledError)
    survivor_ready = clients[1].is_connected
    await asyncio.gather(
        *(client.disconnect() for client in clients),
        return_exceptions=True,
    )
    cleanup_disconnected = not any(client.is_connected for client in clients)

    recovery_clients = [
        BleakClient(device, pair=False, timeout=CONNECT_TIMEOUT_SECONDS) for device in devices
    ]
    try:
        await asyncio.gather(*(client.connect() for client in recovery_clients))
        recovery_results = await asyncio.gather(
            *(_read_only_native_client_workflow(client) for client in recovery_clients)
        )
    finally:
        await asyncio.gather(
            *(client.disconnect() for client in recovery_clients),
            return_exceptions=True,
        )

    return {
        "cancelled": cancelled,
        "cleanup_disconnected": cleanup_disconnected,
        "recovery_disconnected": not any(client.is_connected for client in recovery_clients),
        "recovery_pftp_ready": all(disk_valid for _type_count, disk_valid in recovery_results),
        "recovery_pmd_ready": all(type_count > 0 for type_count, _disk_valid in recovery_results),
        "survivor_ready": survivor_ready,
    }


async def _fresh_bleak_preparation(target: str) -> dict[str, bool]:
    device = await BleakScanner.find_device_by_address(
        target,
        timeout=DISCOVERY_TIMEOUT_SECONDS,
    )
    if device is None:
        raise AssertionError("The reset SPEC-009 target was not observed.")

    initial_client = BleakClient(
        device,
        pair=True,
        timeout=PAIRING_TIMEOUT_SECONDS,
    )
    try:
        await initial_client.connect()
        _assert_required_services(initial_client)
        initial_connection_ready = initial_client.is_connected
    finally:
        await initial_client.disconnect()

    reconnect_device = await BleakScanner.find_device_by_address(
        target,
        timeout=DISCOVERY_TIMEOUT_SECONDS,
    )
    if reconnect_device is None:
        raise AssertionError("The prepared SPEC-009 target was not resolved for reconnect.")
    reconnect_client = BleakClient(
        reconnect_device,
        pair=False,
        timeout=CONNECT_TIMEOUT_SECONDS,
    )
    try:
        await reconnect_client.connect()
        _assert_required_services(reconnect_client)
        reconnect_ready = reconnect_client.is_connected
    finally:
        await reconnect_client.disconnect()

    return {
        "initial_connection_ready": initial_connection_ready,
        "initial_final_connected": initial_client.is_connected,
        "reconnect_ready": reconnect_ready,
        "reconnect_final_connected": reconnect_client.is_connected,
    }


async def _cancellation_cleanup_and_recovery(target: str) -> dict[str, object]:
    scanner_task = asyncio.create_task(
        BleakScanner.find_device_by_address(
            MISSING_DEVICE_ADDRESS,
            timeout=DISCOVERY_TIMEOUT_SECONDS,
        )
    )
    await asyncio.sleep(0.25)
    scanner_task.cancel()
    scanner_cancelled = False
    try:
        await scanner_task
    except asyncio.CancelledError:
        scanner_cancelled = True

    device = await BleakScanner.find_device_by_address(
        target,
        timeout=DISCOVERY_TIMEOUT_SECONDS,
    )
    if device is None:
        raise AssertionError("The authorized SPEC-009 target was not resolved after cancellation.")

    cancelled_client = BleakClient(device, pair=False, timeout=CONNECT_TIMEOUT_SECONDS)
    connect_task = asyncio.create_task(cancelled_client.connect())
    await asyncio.sleep(0.25)
    connect_task.cancel()
    connect_cancelled = False
    try:
        await connect_task
    except asyncio.CancelledError:
        connect_cancelled = True
    finally:
        await cancelled_client.disconnect()

    recovery_device = await BleakScanner.find_device_by_address(
        target,
        timeout=DISCOVERY_TIMEOUT_SECONDS,
    )
    if recovery_device is None:
        raise AssertionError("The authorized SPEC-009 target was not resolved for recovery.")
    recovery_client = BleakClient(
        recovery_device,
        pair=False,
        timeout=CONNECT_TIMEOUT_SECONDS,
    )
    try:
        await recovery_client.connect()
        _assert_required_services(recovery_client)
        recovery_connected = recovery_client.is_connected
    finally:
        await recovery_client.disconnect()

    return {
        "connect_cancelled": connect_cancelled,
        "connected_after_cleanup": cancelled_client.is_connected,
        "recovery_connected": recovery_connected,
        "recovery_final_connected": recovery_client.is_connected,
        "scanner_cancelled": scanner_cancelled,
    }


def _assert_required_services(client: BleakClient) -> None:
    services = {service.uuid.lower() for service in client.services}
    assert PMD_SERVICE in services
    assert PFTP_SERVICE in services
