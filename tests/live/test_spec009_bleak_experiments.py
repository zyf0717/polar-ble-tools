"""Opt-in, non-reset Bleak experiments for SPEC-009.

These probes require an already prepared device in the ignored private
inventory. They never request pairing, remove a bond, write device settings,
control recordings, fetch payloads, or delete device data.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest
from bleak import BleakClient, BleakScanner

from polar_ble_tools.inventory import InventoryError, load_allowed_mac_addresses
from polar_ble_tools.polar.uuids import PFTP_SERVICE, PMD_SERVICE

SPEC009_LIVE_ENV = "POLAR_BLE_SPEC009"
LIVE_MAC_ENV = "POLAR_BLE_LIVE_MAC"
TEST_DEVICES_FILE = Path("test_devices.yaml")
DISCOVERY_TIMEOUT_SECONDS = 10.0
CONNECT_TIMEOUT_SECONDS = 20.0
TEST_TIMEOUT_SECONDS = 60.0
REPEAT_CONNECTIONS = 3
MISSING_DEVICE_ADDRESS = "00:00:00:00:00:00"


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
        allowed = load_allowed_mac_addresses(TEST_DEVICES_FILE)
    except InventoryError as exc:
        raise AssertionError("The SPEC-009 live-test inventory is invalid.") from exc
    normalized = target.upper()
    if normalized not in allowed:
        raise AssertionError("The SPEC-009 live-test target is not authorized.")
    return normalized


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
