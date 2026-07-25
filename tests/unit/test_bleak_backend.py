import asyncio

from polar_ble_tools.ble.bleak_backend import BleakTransport


class FakeBleakDevice:
    address = "AA:BB:CC:DD:EE:FF"
    name = "Polar Loop Gen 2"
    rssi = -45
    details = {"source": "test"}
    metadata = {"uuids": ["feee"]}


class FakeScanner:
    @staticmethod
    async def discover(**kwargs):
        assert kwargs["timeout"] == 0.1
        assert kwargs["service_uuids"] == ["feee"]
        return [FakeBleakDevice()]


class FakeService:
    uuid = "0000feee-0000-1000-8000-00805f9b34fb"


class FakeClient:
    def __init__(self, identifier: str) -> None:
        self.identifier = identifier
        self.is_connected = False
        self.services = [FakeService()]
        self.writes: list[tuple[str, bytes, bool]] = []

    async def connect(self) -> None:
        self.is_connected = True

    async def disconnect(self) -> None:
        self.is_connected = False

    async def read_gatt_char(self, characteristic_uuid: str) -> bytes:
        return characteristic_uuid.encode()

    async def write_gatt_char(
        self,
        characteristic_uuid: str,
        data: bytes,
        *,
        response: bool,
    ) -> None:
        self.writes.append((characteristic_uuid, data, response))

    async def start_notify(self, characteristic_uuid: str, callback) -> None:
        callback(characteristic_uuid, bytearray(b"ok"))

    async def stop_notify(self, characteristic_uuid: str) -> None:
        return None


def test_bleak_transport_scans_and_session_wraps_client() -> None:
    async def run() -> None:
        transport = BleakTransport(scanner_cls=FakeScanner, client_cls=FakeClient)
        devices = await transport.scan(timeout=0.1, service_uuids=["feee"])
        assert devices[0].mac_address == "AA:BB:CC:DD:EE:FF"

        session = await transport.connect("AA:BB:CC:DD:EE:FF")
        assert session.is_connected is True
        assert "0000feee-0000-1000-8000-00805f9b34fb" in session.services
        assert await session.read("test-char") == b"test-char"

        notified: list[bytes] = []
        await session.start_notify("notify-char", lambda _sender, data: notified.append(data))
        assert notified == [b"ok"]

        await session.write("write-char", b"data", response=True)
        await transport.disconnect(session)
        assert session.is_connected is False

    asyncio.run(run())
