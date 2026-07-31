from __future__ import annotations

import asyncio

import pytest

from polar_ble_tools.ble.lifecycle import BleLifecycleState
from polar_ble_tools.ble.transport import BleServiceNotFound, DevicePlatform
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
    services = [
        "0000feee-0000-1000-8000-00805f9b34fb",
        "fb005c80-02e7-f387-1cad-8acd2d8df0c8",
    ]

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
    platform = DevicePlatform.LINUX

    def __init__(self) -> None:
        self.connects: list[str] = []
        self.disconnects = 0
        self.session = FakeBleSession()

    async def scan(
        self, *, timeout: float, name_substring: str | None = None
    ) -> tuple[object, ...]:
        del timeout, name_substring
        return ()

    async def connect(self, identifier: str, *, pair: bool = False) -> FakeBleSession:
        del pair
        self.connects.append(identifier)
        return self.session

    async def disconnect(self, session: FakeBleSession) -> None:
        self.disconnects += 1
        await session.disconnect()


class MissingServiceTransport(FakeTransport):
    async def connect(self, identifier: str, *, pair: bool = False) -> FakeBleSession:
        session = await super().connect(identifier, pair=pair)
        session.services = ["0000feee-0000-1000-8000-00805f9b34fb"]
        return session


class FailingDisconnectTransport(FakeTransport):
    async def disconnect(self, session: FakeBleSession) -> None:
        del session
        self.disconnects += 1
        raise RuntimeError("disconnect failed")


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


def test_open_polar_device_rejects_missing_required_service_and_disconnects() -> None:
    async def run() -> None:
        transport = MissingServiceTransport()
        device = open_polar_device(
            "AA:BB:CC:DD:EE:FF",
            transport_factory=lambda: transport,
        )
        try:
            async with device:
                raise AssertionError("missing service must prevent readiness")
        except BleServiceNotFound:
            pass
        else:
            raise AssertionError("Expected BleServiceNotFound.")
        assert transport.disconnects == 1
        assert device.lifecycle.state == BleLifecycleState.DISCONNECTED

    asyncio.run(run())


def test_readiness_cancellation_disconnects_and_reraises(monkeypatch) -> None:
    async def run() -> None:
        transport = FakeTransport()
        readiness_started = asyncio.Event()

        async def block_readiness(_session, *, timeout: float):
            del timeout
            readiness_started.set()
            await asyncio.Event().wait()

        monkeypatch.setattr(
            "polar_ble_tools.device._wait_for_required_services",
            block_readiness,
        )
        device = open_polar_device(
            "AA:BB:CC:DD:EE:FF",
            transport_factory=lambda: transport,
        )
        task = asyncio.create_task(device.__aenter__())
        await readiness_started.wait()
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task
        assert transport.disconnects == 1

    asyncio.run(run())


def test_public_open_session_serializes_same_identifier() -> None:
    async def run() -> None:
        transports: list[FakeTransport] = []
        first_entered = asyncio.Event()
        release_first = asyncio.Event()
        second_entered = asyncio.Event()

        def factory() -> FakeTransport:
            transport = FakeTransport()
            transports.append(transport)
            return transport

        async def first() -> None:
            async with open_polar_device(
                "aa-bb-cc-dd-ee-ff",
                transport_factory=factory,
            ):
                first_entered.set()
                await release_first.wait()

        async def second() -> None:
            async with open_polar_device(
                "AA:BB:CC:DD:EE:FF",
                transport_factory=factory,
            ):
                second_entered.set()

        first_task = asyncio.create_task(first())
        await first_entered.wait()
        second_task = asyncio.create_task(second())
        await asyncio.sleep(0)
        assert second_entered.is_set() is False
        assert len(transports) == 1

        release_first.set()
        await asyncio.gather(first_task, second_task)
        assert second_entered.is_set() is True
        assert len(transports) == 2

    asyncio.run(run())


def test_cleanup_failure_releases_coordination_for_later_recovery() -> None:
    async def run() -> None:
        failing = FailingDisconnectTransport()
        with pytest.raises(RuntimeError, match="disconnect failed"):
            async with open_polar_device(
                "AA:BB:CC:DD:EE:FF",
                transport_factory=lambda: failing,
            ):
                pass

        recovered = FakeTransport()
        async with asyncio.timeout(1.0):
            async with open_polar_device(
                "AA:BB:CC:DD:EE:FF",
                transport_factory=lambda: recovered,
            ):
                pass
        assert recovered.disconnects == 1

    asyncio.run(run())
