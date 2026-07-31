from __future__ import annotations

import asyncio

import pytest

from polar_ble_tools.ble.bleak_backend import (
    BleakDeviceResolver,
    BleakTransport,
    current_platform,
)
from polar_ble_tools.ble.transport import (
    DeviceLifecycleError,
    DevicePlatform,
    DiscoveredDevice,
    LifecyclePhase,
    LifecycleTimeouts,
)


class FakeBleakDevice:
    def __init__(self, address: str, name: str | None = None) -> None:
        self.address = address
        self.name = name


class FakeAdvertisement:
    def __init__(
        self,
        *,
        local_name: str | None,
        rssi: int | None,
        service_uuids: list[str] | None,
    ) -> None:
        self.local_name = local_name
        self.rssi = rssi
        self.service_uuids = service_uuids


DEVICE = FakeBleakDevice("aa-bb-cc-dd-ee-ff", "fallback")
ADVERTISEMENT = FakeAdvertisement(
    local_name="Polar Loop Gen 2",
    rssi=-45,
    service_uuids=["FEEE", "fb005c80-02e7-f387-1cad-8acd2d8df0c8"],
)


class FakeScanner:
    calls = 0
    release: asyncio.Event | None = None

    @classmethod
    async def discover(cls, **kwargs):
        cls.calls += 1
        assert kwargs["return_adv"] is True
        if cls.release is not None:
            await cls.release.wait()
        return {"one": (DEVICE, ADVERTISEMENT)}


class DuplicateScanner:
    @classmethod
    async def discover(cls, **_kwargs):
        duplicate = FakeBleakDevice("AA:BB:CC:DD:EE:FF")
        missing_identifier = FakeBleakDevice("")
        return {
            "first": (
                DEVICE,
                FakeAdvertisement(
                    local_name="Polar Loop",
                    rssi=-50,
                    service_uuids=["service-b"],
                ),
            ),
            "second": (
                duplicate,
                FakeAdvertisement(
                    local_name=None,
                    rssi=None,
                    service_uuids=["service-a"],
                ),
            ),
            "missing": (
                missing_identifier,
                FakeAdvertisement(local_name=None, rssi=None, service_uuids=None),
            ),
        }


class FakeService:
    def __init__(self, uuid: str) -> None:
        self.uuid = uuid


class FakeClient:
    instances: list[FakeClient] = []
    block_connect = False
    block_disconnect = False
    connect_error: Exception | None = None

    def __init__(self, native, *, pair: bool, timeout: float) -> None:
        assert native is DEVICE
        self.native = native
        self.pair = pair
        self.timeout = timeout
        self.is_connected = False
        self.services = [FakeService("0000feee-0000-1000-8000-00805f9b34fb")]
        self.writes: list[tuple[str, bytes, bool]] = []
        self.connect_started = asyncio.Event()
        self.connect_release = asyncio.Event()
        self.disconnect_calls = 0
        self.disconnect_started = asyncio.Event()
        self.disconnect_release = asyncio.Event()
        self.instances.append(self)

    async def connect(self) -> None:
        self.connect_started.set()
        self.is_connected = True
        if self.connect_error is not None:
            raise self.connect_error
        if self.block_connect:
            await self.connect_release.wait()

    async def disconnect(self) -> None:
        self.disconnect_calls += 1
        self.disconnect_started.set()
        if self.block_disconnect:
            await self.disconnect_release.wait()
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


def setup_function() -> None:
    FakeScanner.calls = 0
    FakeScanner.release = None
    FakeClient.instances.clear()
    FakeClient.block_connect = False
    FakeClient.block_disconnect = False
    FakeClient.connect_error = None


def test_structured_scan_maps_public_fields_and_filters_name() -> None:
    async def run() -> None:
        transport = BleakTransport(
            scanner_cls=FakeScanner,
            client_cls=FakeClient,
            platform=DevicePlatform.LINUX,
        )
        devices = await transport.scan(timeout=0.1, name_substring="loop")

        assert len(devices) == 1
        assert devices[0].to_jsonable() == {
            "identifier": "AA:BB:CC:DD:EE:FF",
            "platform": "linux",
            "name": "Polar Loop Gen 2",
            "rssi": -45,
            "service_uuids": [
                "fb005c80-02e7-f387-1cad-8acd2d8df0c8",
                "feee",
            ],
        }
        assert await transport.scan(timeout=0.1, name_substring="verity") == ()

    asyncio.run(run())


def test_structured_scan_deduplicates_and_tolerates_missing_fields() -> None:
    async def run() -> None:
        transport = BleakTransport(
            scanner_cls=DuplicateScanner,
            client_cls=FakeClient,
            platform=DevicePlatform.WINDOWS,
        )
        devices = await transport.scan(timeout=0.1)

        assert len(devices) == 1
        assert devices[0] == DiscoveredDevice(
            identifier="AA:BB:CC:DD:EE:FF",
            platform=DevicePlatform.WINDOWS,
            name="Polar Loop",
            rssi=-50,
            service_uuids=("service-a", "service-b"),
        )

    asyncio.run(run())


def test_transport_constructs_client_from_current_native_device() -> None:
    async def run() -> None:
        transport = BleakTransport(
            scanner_cls=FakeScanner,
            client_cls=FakeClient,
            platform=DevicePlatform.LINUX,
        )
        session = await transport.connect("AA:BB:CC:DD:EE:FF")

        assert FakeClient.instances[0].native is DEVICE
        assert FakeClient.instances[0].pair is False
        assert await session.read("test-char") == b"test-char"
        await session.write("write-char", b"data", response=True)
        await transport.disconnect(session)
        assert session.is_connected is False

    asyncio.run(run())


def test_concurrent_resolutions_share_one_structured_scan() -> None:
    async def run() -> None:
        FakeScanner.release = asyncio.Event()
        resolver = BleakDeviceResolver(FakeScanner, platform=DevicePlatform.LINUX)
        first = asyncio.create_task(resolver.resolve("AA:BB:CC:DD:EE:FF", timeout=1.0))
        second = asyncio.create_task(resolver.resolve("aa-bb-cc-dd-ee-ff", timeout=1.0))
        await asyncio.sleep(0)
        FakeScanner.release.set()
        resolved = await asyncio.gather(first, second)

        assert FakeScanner.calls == 1
        assert resolved[0].native is DEVICE
        assert resolved[1].native is DEVICE

    asyncio.run(run())


def test_cancelled_resolution_does_not_cancel_shared_scan() -> None:
    async def run() -> None:
        FakeScanner.release = asyncio.Event()
        resolver = BleakDeviceResolver(FakeScanner, platform=DevicePlatform.LINUX)
        cancelled = asyncio.create_task(resolver.resolve("AA:BB:CC:DD:EE:FF", timeout=1.0))
        survivor = asyncio.create_task(resolver.resolve("AA:BB:CC:DD:EE:FF", timeout=1.0))
        await asyncio.sleep(0)
        cancelled.cancel()
        with pytest.raises(asyncio.CancelledError):
            await cancelled
        FakeScanner.release.set()

        assert (await survivor).native is DEVICE
        assert resolver.cancelled_phase is LifecyclePhase.DISCOVERY
        assert FakeScanner.calls == 1

    asyncio.run(run())


def test_connect_cancellation_disconnects_partial_client() -> None:
    async def run() -> None:
        FakeClient.block_connect = True
        transport = BleakTransport(
            scanner_cls=FakeScanner,
            client_cls=FakeClient,
            platform=DevicePlatform.LINUX,
            timeouts=LifecycleTimeouts(connect=1.0, disconnect=1.0),
        )
        task = asyncio.create_task(transport.connect("AA:BB:CC:DD:EE:FF"))
        while not FakeClient.instances:
            await asyncio.sleep(0)
        await FakeClient.instances[0].connect_started.wait()
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task
        assert FakeClient.instances[0].disconnect_calls == 1
        assert FakeClient.instances[0].is_connected is False

    asyncio.run(run())


@pytest.mark.parametrize(
    ("message", "phase"),
    [
        ("org.bluez.Error.AuthenticationFailed", LifecyclePhase.PREPARATION),
        ("connection attempt failed", LifecyclePhase.CONNECT),
    ],
)
def test_connect_failure_normalizes_authentication_phase(
    message: str,
    phase: LifecyclePhase,
) -> None:
    async def run() -> None:
        FakeClient.connect_error = RuntimeError(message)
        transport = BleakTransport(
            scanner_cls=FakeScanner,
            client_cls=FakeClient,
            platform=DevicePlatform.LINUX,
        )

        with pytest.raises(DeviceLifecycleError) as captured:
            await transport.connect("AA:BB:CC:DD:EE:FF")
        assert captured.value.phase is phase
        assert FakeClient.instances[0].disconnect_calls == 1

    asyncio.run(run())


def test_disconnect_cancellation_finishes_cleanup_and_reraises() -> None:
    async def run() -> None:
        FakeClient.block_disconnect = True
        transport = BleakTransport(
            scanner_cls=FakeScanner,
            client_cls=FakeClient,
            platform=DevicePlatform.LINUX,
            timeouts=LifecycleTimeouts(connect=1.0, disconnect=1.0),
        )
        session = await transport.connect("AA:BB:CC:DD:EE:FF")
        client = FakeClient.instances[0]
        task = asyncio.create_task(transport.disconnect(session))
        await client.disconnect_started.wait()
        task.cancel()
        client.disconnect_release.set()

        with pytest.raises(asyncio.CancelledError):
            await task
        assert client.is_connected is False
        assert transport.cancelled_phase is LifecyclePhase.DISCONNECT

    asyncio.run(run())


def test_disconnect_timeout_has_typed_phase() -> None:
    async def run() -> None:
        FakeClient.block_disconnect = True
        transport = BleakTransport(
            scanner_cls=FakeScanner,
            client_cls=FakeClient,
            platform=DevicePlatform.LINUX,
            timeouts=LifecycleTimeouts(connect=1.0, disconnect=0.01),
        )
        session = await transport.connect("AA:BB:CC:DD:EE:FF")
        with pytest.raises(DeviceLifecycleError) as captured:
            await transport.disconnect(session)
        assert captured.value.phase is LifecyclePhase.DISCONNECT

    asyncio.run(run())


def test_resolution_reports_distinct_phase_when_target_is_not_observed() -> None:
    async def run() -> None:
        resolver = BleakDeviceResolver(FakeScanner, platform=DevicePlatform.LINUX)
        with pytest.raises(DeviceLifecycleError) as captured:
            await resolver.resolve("11:22:33:44:55:66", timeout=0.1)
        assert captured.value.phase is LifecyclePhase.RESOLUTION

    asyncio.run(run())


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("linux", DevicePlatform.LINUX),
        ("linux2", DevicePlatform.LINUX),
        ("darwin", DevicePlatform.MACOS),
        ("win32", DevicePlatform.WINDOWS),
    ],
)
def test_platform_selection(value: str, expected: DevicePlatform) -> None:
    assert current_platform(value) is expected


def test_platform_selection_rejects_unknown_backend() -> None:
    with pytest.raises(DeviceLifecycleError) as captured:
        current_platform("freebsd")
    assert captured.value.phase is LifecyclePhase.UNSUPPORTED
