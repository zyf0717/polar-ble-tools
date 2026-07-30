from __future__ import annotations

import asyncio

from polar_ble_tools.workflows import DeviceLockRegistry, DeviceWorkflowRunner


class FakeSession:
    is_connected = True
    services: list[str] = []

    async def disconnect(self) -> None:
        return None

    async def read(self, _characteristic: str) -> bytes:
        return b""

    async def write(self, _characteristic: str, _data: bytes, *, response=False) -> None:
        return None

    async def start_notify(self, _characteristic: str, _callback) -> None:
        return None

    async def stop_notify(self, _characteristic: str) -> None:
        return None


class FakeTransport:
    def __init__(self) -> None:
        self.connected: list[str] = []
        self.disconnected = 0

    async def connect(self, identifier: str) -> FakeSession:
        self.connected.append(identifier)
        return FakeSession()

    async def disconnect(self, _session: FakeSession) -> None:
        self.disconnected += 1


def test_workflow_runner_owns_one_connected_session() -> None:
    async def run() -> None:
        transport = FakeTransport()
        runner = DeviceWorkflowRunner(transport_factory=lambda: transport)
        result = await runner.run("aa-bb-cc-dd-ee-ff", lambda device: _target(device))
        assert result == "AA:BB:CC:DD:EE:FF"
        assert transport.connected == ["AA:BB:CC:DD:EE:FF"]
        assert transport.disconnected == 1

    asyncio.run(run())


def test_workflow_runner_serializes_same_device_deterministically() -> None:
    async def run() -> None:
        runner = DeviceWorkflowRunner(
            transport_factory=FakeTransport,
            lock_registry=DeviceLockRegistry(),
        )
        first_entered = asyncio.Event()
        release_first = asyncio.Event()
        second_requested = asyncio.Event()
        second_entered = asyncio.Event()
        order: list[str] = []

        async def first(_device) -> str:
            order.append("first_enter")
            first_entered.set()
            await release_first.wait()
            order.append("first_exit")
            return "first"

        async def second(_device) -> str:
            order.append("second_enter")
            second_entered.set()
            return "second"

        async def request_second() -> str:
            second_requested.set()
            return await runner.run("AA:BB:CC:DD:EE:FF", second)

        first_task = asyncio.create_task(runner.run("aa-bb-cc-dd-ee-ff", first))
        await asyncio.wait_for(first_entered.wait(), timeout=1.0)
        second_task = asyncio.create_task(request_second())
        await asyncio.wait_for(second_requested.wait(), timeout=1.0)
        await asyncio.sleep(0)
        assert second_entered.is_set() is False
        release_first.set()

        assert await asyncio.wait_for(
            asyncio.gather(first_task, second_task),
            timeout=1.0,
        ) == ["first", "second"]
        assert order == ["first_enter", "first_exit", "second_enter"]

    asyncio.run(run())


def test_workflow_runner_allows_distinct_devices_to_overlap() -> None:
    async def run() -> None:
        runner = DeviceWorkflowRunner(
            transport_factory=FakeTransport,
            lock_registry=DeviceLockRegistry(),
        )
        both_entered = asyncio.Event()
        entered: set[str] = set()

        async def workflow(device) -> str:
            entered.add(device.target.identifier)
            if len(entered) == 2:
                both_entered.set()
            await asyncio.wait_for(both_entered.wait(), timeout=1.0)
            return device.target.identifier

        results = await asyncio.wait_for(
            asyncio.gather(
                runner.run("AA:BB:CC:DD:EE:FF", workflow),
                runner.run("11:22:33:44:55:66", workflow),
            ),
            timeout=1.0,
        )

        assert set(results) == {"AA:BB:CC:DD:EE:FF", "11:22:33:44:55:66"}
        assert entered == set(results)

    asyncio.run(run())


async def _target(device) -> str:
    return device.target.identifier
