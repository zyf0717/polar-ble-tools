from __future__ import annotations

import asyncio

from polar_ble_tools.ble.lifecycle import BleLifecycleState
from polar_ble_tools.device import (
    PolarDeviceSessionError,
    PolarDeviceTarget,
    PolarDeviceTargetError,
    open_polar_device,
    resolve_polar_device_target,
)
from polar_ble_tools.polar.pftp import PftpClient
from polar_ble_tools.polar.setup import PolarSetupClient


class FakeBleSession:
    is_connected = True
    services = ["0000feee-0000-1000-8000-00805f9b34fb"]

    async def disconnect(self) -> None:
        self.is_connected = False

    async def read(self, characteristic_uuid: str) -> bytes:
        return characteristic_uuid.encode()

    async def write(
        self,
        characteristic_uuid: str,
        data: bytes,
        *,
        response: bool = False,
    ) -> None:
        del characteristic_uuid, data, response

    async def start_notify(self, characteristic_uuid: str, callback: object) -> None:
        del characteristic_uuid, callback

    async def stop_notify(self, characteristic_uuid: str) -> None:
        del characteristic_uuid


class FakeTransport:
    def __init__(self) -> None:
        self.connects: list[str] = []
        self.disconnects = 0
        self.session = FakeBleSession()

    async def scan(self, *, timeout: float, service_uuids: object = None) -> list[object]:
        del timeout, service_uuids
        return []

    async def connect(self, identifier: str) -> FakeBleSession:
        self.connects.append(identifier)
        return self.session

    async def disconnect(self, session: FakeBleSession) -> None:
        self.disconnects += 1
        await session.disconnect()


def test_resolve_polar_device_target_normalizes_mac_variants() -> None:
    target = resolve_polar_device_target(
        PolarDeviceTarget(identifier=" aa-bb-cc-dd-ee-ff ", name="Loop", metadata={"slot": 1})
    )

    assert target.identifier == "AA:BB:CC:DD:EE:FF"
    assert target.device_id == "AA:BB:CC:DD:EE:FF"
    assert target.name == "Loop"
    assert target.metadata == {"slot": 1}


def test_resolve_polar_device_target_rejects_empty_identifier() -> None:
    try:
        resolve_polar_device_target("   ")
    except PolarDeviceTargetError as exc:
        assert "identifier is empty" in str(exc)
    else:
        raise AssertionError("Expected PolarDeviceTargetError.")


def test_open_polar_device_manages_ftu_services_and_disconnects() -> None:
    async def run() -> None:
        transports: list[FakeTransport] = []

        def factory() -> FakeTransport:
            transport = FakeTransport()
            transports.append(transport)
            return transport

        async with open_polar_device("aa-bb-cc-dd-ee-ff", transport_factory=factory) as device:
            assert device.target.identifier == "AA:BB:CC:DD:EE:FF"
            assert isinstance(device.services.pftp, PftpClient)
            assert isinstance(device.services.setup, PolarSetupClient)
            async with device.operation_lock:
                assert device.operation_lock.locked()

        assert transports[0].connects == ["AA:BB:CC:DD:EE:FF"]
        assert transports[0].disconnects == 1
        assert device.lifecycle.state == BleLifecycleState.DISCONNECTED

    asyncio.run(run())


def test_services_are_unavailable_after_session_closes() -> None:
    async def run() -> None:
        device = open_polar_device("AA:BB:CC:DD:EE:FF", transport_factory=FakeTransport)
        async with device:
            assert device.services.setup is not None

        for property_name, message in (
            ("services", "services are not ready"),
            ("session", "session is not connected"),
        ):
            try:
                getattr(device, property_name)
            except PolarDeviceSessionError as exc:
                assert message in str(exc)
            else:
                raise AssertionError("Expected PolarDeviceSessionError.")

    asyncio.run(run())
