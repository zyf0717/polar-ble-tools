from __future__ import annotations

import asyncio

from polar_ble_tools.workflows import DeviceWorkflowRunner


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


async def _target(device) -> str:
    return device.target.identifier
