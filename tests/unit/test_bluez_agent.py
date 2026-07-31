from __future__ import annotations

import asyncio

import pytest
from dbus_fast import DBusError

from polar_ble_tools.ble.bluez_agent import (
    AGENT_PATH,
    LinuxAuthenticationAgent,
    TargetBoundAgent,
)
from polar_ble_tools.ble.transport import DeviceLifecycleError, LifecyclePhase
from polar_ble_tools.polar.uuids import PMD_SERVICE

TARGET = "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF"
OTHER = "/org/bluez/hci0/dev_11_22_33_44_55_66"


def test_agent_accepts_only_target_bound_supported_callbacks() -> None:
    agent = TargetBoundAgent("AA:BB:CC:DD:EE:FF")

    agent.request_confirmation(TARGET, 123456)
    agent.request_authorization(TARGET)
    agent.authorize_service(TARGET, PMD_SERVICE)
    agent.display_pin_code(TARGET, "123456")
    agent.display_passkey(TARGET, 123456, 0)
    agent.release()
    agent.cancel()
    assert agent.released is True
    assert agent.cancelled is True

    with pytest.raises(DBusError):
        agent.request_authorization(OTHER)
    with pytest.raises(DBusError):
        agent.request_pin_code(TARGET)
    with pytest.raises(DBusError):
        agent.request_passkey(TARGET)
    with pytest.raises(DBusError):
        agent.authorize_service(TARGET, "unsupported")


class FakeManager:
    def __init__(self, *, fail_default: bool = False, block_registration: bool = False) -> None:
        self.fail_default = fail_default
        self.block_registration = block_registration
        self.calls: list[tuple[str, object]] = []

    async def call_register_agent(self, path: str, capability: str) -> None:
        self.calls.append(("register", (path, capability)))
        if self.block_registration:
            await asyncio.Event().wait()

    async def call_request_default_agent(self, path: str) -> None:
        self.calls.append(("default", path))
        if self.fail_default:
            raise RuntimeError("not permitted")

    async def call_unregister_agent(self, path: str) -> None:
        self.calls.append(("unregister", path))


class FakeProxy:
    def __init__(self, manager: FakeManager) -> None:
        self.manager = manager

    def get_interface(self, _name: str) -> FakeManager:
        return self.manager


class FakeBus:
    def __init__(self, manager: FakeManager) -> None:
        self.manager = manager
        self.exported: list[str] = []
        self.unexported: list[str] = []
        self.disconnected = False

    async def connect(self) -> FakeBus:
        return self

    def export(self, path: str, _agent: object) -> None:
        self.exported.append(path)

    async def introspect(self, _service: str, _path: str) -> object:
        return object()

    def get_proxy_object(self, _service: str, _path: str, _introspection: object) -> FakeProxy:
        return FakeProxy(self.manager)

    def unexport(self, path: str, _agent: object) -> None:
        self.unexported.append(path)

    def disconnect(self) -> None:
        self.disconnected = True


def test_linux_agent_unregisters_after_success() -> None:
    async def run() -> None:
        manager = FakeManager()
        bus = FakeBus(manager)
        async with LinuxAuthenticationAgent(
            "AA:BB:CC:DD:EE:FF",
            bus_factory=lambda **_: bus,
        ):
            assert bus.exported == [AGENT_PATH]

        assert [name for name, _value in manager.calls] == [
            "register",
            "default",
            "unregister",
        ]
        assert bus.unexported == [AGENT_PATH]
        assert bus.disconnected is True

    asyncio.run(run())


def test_linux_agent_cleans_registration_when_default_request_fails() -> None:
    async def run() -> None:
        manager = FakeManager(fail_default=True)
        bus = FakeBus(manager)
        with pytest.raises(DeviceLifecycleError) as captured:
            async with LinuxAuthenticationAgent(
                "AA:BB:CC:DD:EE:FF",
                bus_factory=lambda **_: bus,
            ):
                raise AssertionError("agent context must not open")
        assert captured.value.phase is LifecyclePhase.PREPARATION
        assert [name for name, _value in manager.calls] == [
            "register",
            "default",
            "unregister",
        ]
        assert bus.disconnected is True

    asyncio.run(run())


def test_linux_agent_bounds_registration_and_disconnects_bus() -> None:
    async def run() -> None:
        manager = FakeManager(block_registration=True)
        bus = FakeBus(manager)
        with pytest.raises(DeviceLifecycleError) as captured:
            async with LinuxAuthenticationAgent(
                "AA:BB:CC:DD:EE:FF",
                bus_factory=lambda **_: bus,
                timeout=0.01,
            ):
                raise AssertionError("agent context must not open")
        assert captured.value.phase is LifecyclePhase.PREPARATION
        assert [name for name, _value in manager.calls] == [
            "register",
            "unregister",
        ]
        assert bus.disconnected is True

    asyncio.run(run())


def test_linux_agent_registration_is_serialized_per_event_loop() -> None:
    async def run() -> None:
        first_bus = FakeBus(FakeManager())
        second_bus = FakeBus(FakeManager())
        first = LinuxAuthenticationAgent(
            "AA:BB:CC:DD:EE:FF",
            bus_factory=lambda **_: first_bus,
        )
        second = LinuxAuthenticationAgent(
            "11:22:33:44:55:66",
            bus_factory=lambda **_: second_bus,
        )

        await first.__aenter__()
        second_entry = asyncio.create_task(second.__aenter__())
        await asyncio.sleep(0)
        assert second_bus.exported == []

        await first.__aexit__(None, None, None)
        await second_entry
        assert second_bus.exported == [AGENT_PATH]
        await second.__aexit__(None, None, None)

    asyncio.run(run())
