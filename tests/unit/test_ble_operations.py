from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

from polar_ble_tools.ble.operations import prepare_device, probe_device, scan_devices
from polar_ble_tools.ble.transport import (
    BleConnectionError,
    DeviceLifecycleError,
    DevicePlatform,
    DiscoveredDevice,
    LifecyclePhase,
    LifecycleTimeouts,
    PreparationOutcome,
    ReconnectPersistence,
)
from polar_ble_tools.polar.uuids import PFTP_SERVICE, PMD_SERVICE


class FakeSession:
    def __init__(self, services: tuple[str, ...] = (PFTP_SERVICE, PMD_SERVICE)) -> None:
        self.is_connected = True
        self.services = services

    async def disconnect(self) -> None:
        self.is_connected = False

    async def read(self, _characteristic: str) -> bytes:
        return b""

    async def write(self, _characteristic: str, _data: bytes, *, response=False) -> None:
        return None

    async def start_notify(self, _characteristic: str, _callback) -> None:
        return None

    async def stop_notify(self, _characteristic: str) -> None:
        return None


class FakeTransport:
    platform = DevicePlatform.LINUX

    def __init__(self, *, failure: Exception | None = None) -> None:
        self.failure = failure
        self.connect_calls: list[tuple[str, bool]] = []
        self.disconnect_calls = 0

    async def scan(self, *, timeout: float, name_substring: str | None = None):
        assert timeout == 2.0
        assert name_substring == "Polar"
        return (
            DiscoveredDevice(
                identifier="AA:BB:CC:DD:EE:FF",
                platform=DevicePlatform.LINUX,
                name="Polar Loop",
                rssi=-50,
                service_uuids=(PFTP_SERVICE, PMD_SERVICE),
            ),
        )

    async def connect(self, identifier: str, *, pair: bool = False) -> FakeSession:
        self.connect_calls.append((identifier, pair))
        if self.failure is not None:
            raise self.failure
        return FakeSession()

    async def disconnect(self, session: FakeSession) -> None:
        self.disconnect_calls += 1
        await session.disconnect()


def test_scan_devices_delegates_to_structured_transport() -> None:
    async def run() -> None:
        transport = FakeTransport()
        devices = await scan_devices(
            timeout=2.0,
            name_substring="Polar",
            transport_factory=lambda: transport,
        )
        assert devices[0].identifier == "AA:BB:CC:DD:EE:FF"

    asyncio.run(run())


def test_probe_device_verifies_services_and_ends_disconnected(tmp_path: Path) -> None:
    async def run() -> None:
        inventory = tmp_path / "devices.yaml"
        inventory.write_text("lab:\n  - AA:BB:CC:DD:EE:FF\n", encoding="utf-8")
        transport = FakeTransport()
        result = await probe_device(
            "aa-bb-cc-dd-ee-ff",
            devices_file=inventory,
            transport_factory=lambda: transport,
        )

        assert result.readiness_verified is True
        assert result.final_connected is False
        assert result.service_uuids == tuple(sorted((PFTP_SERVICE, PMD_SERVICE)))
        assert transport.disconnect_calls == 1

    asyncio.run(run())


def test_prepare_returns_already_ready_without_agent() -> None:
    async def run() -> None:
        transport = FakeTransport()
        result = await prepare_device(
            "AA:BB:CC:DD:EE:FF",
            transport_factory=lambda: transport,
        )

        assert result.outcome is PreparationOutcome.ALREADY_READY
        assert result.reconnect_persistence is ReconnectPersistence.VERIFIED
        assert transport.connect_calls == [("AA:BB:CC:DD:EE:FF", False)]

    asyncio.run(run())


def test_prepare_uses_target_bound_agent_then_verifies_agent_free_reconnect(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "polar_ble_tools.ble.operations.current_platform",
        lambda: DevicePlatform.LINUX,
    )

    async def run() -> None:
        transports = [
            FakeTransport(
                failure=BleConnectionError(
                    LifecyclePhase.PREPARATION,
                    "authentication required",
                )
            ),
            FakeTransport(),
            FakeTransport(),
        ]
        agent_events: list[tuple[str, str]] = []

        def transport_factory() -> FakeTransport:
            return transports.pop(0)

        @asynccontextmanager
        async def agent_factory(identifier: str):
            agent_events.append(("enter", identifier))
            try:
                yield
            finally:
                agent_events.append(("exit", identifier))

        result = await prepare_device(
            "AA:BB:CC:DD:EE:FF",
            transport_factory=transport_factory,
            agent_factory=agent_factory,
        )

        assert result.outcome is PreparationOutcome.READY
        assert result.reconnect_persistence is ReconnectPersistence.VERIFIED
        assert agent_events == [
            ("enter", "AA:BB:CC:DD:EE:FF"),
            ("exit", "AA:BB:CC:DD:EE:FF"),
        ]

    asyncio.run(run())


def test_non_linux_preparation_does_not_import_or_use_bluez_agent(monkeypatch) -> None:
    monkeypatch.setattr(
        "polar_ble_tools.ble.operations.current_platform",
        lambda: DevicePlatform.WINDOWS,
    )

    async def run() -> None:
        transports = [
            FakeTransport(
                failure=BleConnectionError(
                    LifecyclePhase.PREPARATION,
                    "authentication required",
                )
            ),
            FakeTransport(),
            FakeTransport(),
        ]

        def transport_factory() -> FakeTransport:
            return transports.pop(0)

        def forbidden_agent(_identifier: str):
            raise AssertionError("non-Linux preparation must not use the BlueZ adapter")

        result = await prepare_device(
            "opaque-windows-id",
            transport_factory=transport_factory,
            agent_factory=forbidden_agent,
        )

        assert result.outcome is PreparationOutcome.READY
        assert result.reconnect_persistence is ReconnectPersistence.VERIFIED

    asyncio.run(run())


def test_prepare_does_not_pair_after_non_connect_failure() -> None:
    async def run() -> None:
        transport = FakeTransport(
            failure=BleConnectionError(LifecyclePhase.RESOLUTION, "not observed")
        )
        with pytest.raises(BleConnectionError) as captured:
            await prepare_device(
                "AA:BB:CC:DD:EE:FF",
                transport_factory=lambda: transport,
            )
        assert captured.value.phase is LifecyclePhase.RESOLUTION

    asyncio.run(run())


def test_preparation_timeout_unregisters_agent_and_preserves_phase(monkeypatch) -> None:
    monkeypatch.setattr(
        "polar_ble_tools.ble.operations.current_platform",
        lambda: DevicePlatform.LINUX,
    )

    class BlockingTransport(FakeTransport):
        async def connect(self, identifier: str, *, pair: bool = False) -> FakeSession:
            self.connect_calls.append((identifier, pair))
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

    async def run() -> None:
        transports = [
            FakeTransport(
                failure=BleConnectionError(
                    LifecyclePhase.PREPARATION,
                    "authentication required",
                )
            ),
            BlockingTransport(),
        ]
        agent_events: list[str] = []

        def transport_factory() -> FakeTransport:
            return transports.pop(0)

        @asynccontextmanager
        async def agent_factory(_identifier: str):
            agent_events.append("enter")
            try:
                yield
            finally:
                agent_events.append("exit")

        with pytest.raises(DeviceLifecycleError) as captured:
            await prepare_device(
                "AA:BB:CC:DD:EE:FF",
                timeouts=LifecycleTimeouts(preparation=0.01),
                transport_factory=transport_factory,
                agent_factory=agent_factory,
            )

        assert captured.value.phase is LifecyclePhase.PREPARATION
        assert agent_events == ["enter", "exit"]

    asyncio.run(run())
