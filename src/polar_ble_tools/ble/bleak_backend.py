from __future__ import annotations

import asyncio
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from weakref import WeakKeyDictionary

from polar_ble_tools.ble.transport import (
    BleConnectionError,
    BleSession,
    BleTransportError,
    DeviceLifecycleError,
    DevicePlatform,
    DiscoveredDevice,
    LifecyclePhase,
    LifecycleTimeouts,
    NotifyCallback,
)
from polar_ble_tools.inventory import identifier_key, normalize_identifier


def current_platform(platform_name: str | None = None) -> DevicePlatform:
    value = sys.platform if platform_name is None else platform_name
    if value.startswith("linux"):
        return DevicePlatform.LINUX
    if value == "darwin":
        return DevicePlatform.MACOS
    if value in {"win32", "cygwin"}:
        return DevicePlatform.WINDOWS
    raise DeviceLifecycleError(
        LifecyclePhase.UNSUPPORTED,
        f"BLE platform {value!r} is unsupported.",
    )


@dataclass(frozen=True)
class _NativeObservation:
    public: DiscoveredDevice
    native: Any


class BleakDeviceResolver:
    """Coalesce current-loop scans and keep native devices private."""

    def __init__(self, scanner_cls: Any, *, platform: DevicePlatform) -> None:
        self._scanner_cls = scanner_cls
        self._platform = platform
        self._inflight: WeakKeyDictionary[
            asyncio.AbstractEventLoop,
            asyncio.Task[tuple[_NativeObservation, ...]],
        ] = WeakKeyDictionary()
        self.cancelled_phase: LifecyclePhase | None = None

    async def scan(
        self,
        *,
        timeout: float,
        name_substring: str | None = None,
    ) -> tuple[DiscoveredDevice, ...]:
        observations = await self._observations(timeout)
        name_filter = name_substring.casefold() if name_substring else None
        devices = (
            item.public
            for item in observations
            if name_filter is None
            or (item.public.name is not None and name_filter in item.public.name.casefold())
        )
        return tuple(sorted(devices, key=lambda item: identifier_key(item.identifier)))

    async def resolve(self, identifier: str, *, timeout: float) -> _NativeObservation:
        target_key = identifier_key(identifier)
        for observation in await self._observations(timeout):
            if identifier_key(observation.public.identifier) == target_key:
                return observation
        raise DeviceLifecycleError(
            LifecyclePhase.RESOLUTION,
            "The selected device was not observed during bounded discovery.",
        )

    async def _observations(self, timeout: float) -> tuple[_NativeObservation, ...]:
        loop = asyncio.get_running_loop()
        task = self._inflight.get(loop)
        if task is None:
            task = loop.create_task(self._discover(timeout))
            self._inflight[loop] = task
            task.add_done_callback(
                lambda completed, active_loop=loop: self._finish(active_loop, completed)
            )
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            self.cancelled_phase = LifecyclePhase.DISCOVERY
            raise
        except DeviceLifecycleError:
            raise
        except Exception as exc:
            raise DeviceLifecycleError(
                LifecyclePhase.DISCOVERY,
                "Structured BLE discovery failed.",
            ) from exc

    def _finish(
        self,
        loop: asyncio.AbstractEventLoop,
        task: asyncio.Task[tuple[_NativeObservation, ...]],
    ) -> None:
        if self._inflight.get(loop) is task:
            self._inflight.pop(loop, None)

    async def _discover(self, timeout: float) -> tuple[_NativeObservation, ...]:
        try:
            raw = await asyncio.wait_for(
                self._scanner_cls.discover(timeout=timeout, return_adv=True),
                timeout=timeout + 1.0,
            )
        except TimeoutError as exc:
            raise DeviceLifecycleError(
                LifecyclePhase.DISCOVERY,
                "Structured BLE discovery timed out.",
            ) from exc
        observations: dict[str, _NativeObservation] = {}
        values = raw.values() if isinstance(raw, dict) else raw
        for value in values:
            if not isinstance(value, tuple) or len(value) != 2:
                raise DeviceLifecycleError(
                    LifecyclePhase.DISCOVERY,
                    "The Bleak scanner did not return advertisement data.",
                )
            native, advertisement = value
            raw_identifier = str(getattr(native, "address", "") or "")
            try:
                identifier = normalize_identifier(raw_identifier)
            except ValueError:
                continue
            name = getattr(advertisement, "local_name", None) or getattr(native, "name", None)
            service_uuids = tuple(
                sorted(
                    {
                        str(item).lower()
                        for item in (getattr(advertisement, "service_uuids", None) or ())
                    }
                )
            )
            public = DiscoveredDevice(
                identifier=identifier,
                platform=self._platform,
                name=str(name) if name else None,
                rssi=getattr(advertisement, "rssi", None),
                service_uuids=service_uuids,
            )
            key = identifier_key(identifier)
            previous = observations.get(key)
            if previous is not None:
                public = DiscoveredDevice(
                    identifier=identifier,
                    platform=self._platform,
                    name=public.name or previous.public.name,
                    rssi=public.rssi if public.rssi is not None else previous.public.rssi,
                    service_uuids=tuple(
                        sorted({*previous.public.service_uuids, *public.service_uuids})
                    ),
                )
            observations[key] = _NativeObservation(public, native)
        return tuple(observations.values())


_RESOLVERS: WeakKeyDictionary[Any, dict[DevicePlatform, BleakDeviceResolver]] = WeakKeyDictionary()


def _resolver_for(scanner_cls: Any, platform: DevicePlatform) -> BleakDeviceResolver:
    by_platform = _RESOLVERS.get(scanner_cls)
    if by_platform is None:
        by_platform = {}
        _RESOLVERS[scanner_cls] = by_platform
    resolver = by_platform.get(platform)
    if resolver is None:
        resolver = BleakDeviceResolver(scanner_cls, platform=platform)
        by_platform[platform] = resolver
    return resolver


class BleakSession:
    def __init__(self, client: Any) -> None:
        self._client = client

    @property
    def is_connected(self) -> bool:
        connected = getattr(self._client, "is_connected", False)
        return connected() if callable(connected) else bool(connected)

    @property
    def services(self) -> Sequence[str]:
        services = getattr(self._client, "services", None)
        if services is None:
            return ()
        return tuple(str(getattr(service, "uuid", service)).lower() for service in services)

    async def disconnect(self) -> None:
        await self._client.disconnect()

    async def read(self, characteristic_uuid: str) -> bytes:
        try:
            return bytes(await self._client.read_gatt_char(characteristic_uuid))
        except Exception as exc:  # pragma: no cover - backend normalization
            raise BleTransportError(
                LifecyclePhase.SERVICE_READINESS,
                f"BLE read failed for {characteristic_uuid}.",
            ) from exc

    async def write(
        self,
        characteristic_uuid: str,
        data: bytes,
        *,
        response: bool = False,
    ) -> None:
        try:
            await self._client.write_gatt_char(
                characteristic_uuid,
                data,
                response=response,
            )
        except Exception as exc:  # pragma: no cover - backend normalization
            raise BleTransportError(
                LifecyclePhase.SERVICE_READINESS,
                f"BLE write failed for {characteristic_uuid}.",
            ) from exc

    async def start_notify(
        self,
        characteristic_uuid: str,
        callback: NotifyCallback,
    ) -> None:
        def wrapped(sender: object, data: bytearray) -> None:
            callback(str(sender), bytes(data))

        try:
            await self._client.start_notify(characteristic_uuid, wrapped)
        except Exception as exc:  # pragma: no cover - backend normalization
            raise BleTransportError(
                LifecyclePhase.SERVICE_READINESS,
                f"BLE notification setup failed for {characteristic_uuid}.",
            ) from exc

    async def stop_notify(self, characteristic_uuid: str) -> None:
        try:
            await self._client.stop_notify(characteristic_uuid)
        except Exception as exc:  # pragma: no cover - backend normalization
            raise BleTransportError(
                LifecyclePhase.DISCONNECT,
                f"BLE notification cleanup failed for {characteristic_uuid}.",
            ) from exc


class BleakTransport:
    def __init__(
        self,
        *,
        scanner_cls: Any | None = None,
        client_cls: Any | None = None,
        resolver: BleakDeviceResolver | None = None,
        platform: DevicePlatform | None = None,
        timeouts: LifecycleTimeouts | None = None,
    ) -> None:
        if scanner_cls is None or client_cls is None:
            from bleak import BleakClient, BleakScanner

            scanner_cls = scanner_cls or BleakScanner
            client_cls = client_cls or BleakClient
        self.platform = platform or current_platform()
        self.timeouts = timeouts or LifecycleTimeouts()
        self._client_cls = client_cls
        self._resolver = resolver or _resolver_for(scanner_cls, self.platform)
        self.cancelled_phase: LifecyclePhase | None = None

    async def scan(
        self,
        *,
        timeout: float,
        name_substring: str | None = None,
    ) -> tuple[DiscoveredDevice, ...]:
        return await self._resolver.scan(timeout=timeout, name_substring=name_substring)

    async def connect(self, identifier: str, *, pair: bool = False) -> BleSession:
        observation = await self._resolver.resolve(
            normalize_identifier(identifier),
            timeout=self.timeouts.resolution,
        )
        client = self._client_cls(
            observation.native,
            pair=pair,
            timeout=self.timeouts.connect,
        )
        try:
            await asyncio.wait_for(client.connect(), timeout=self.timeouts.connect)
        except BaseException as exc:
            phase = _connection_failure_phase(exc, pair=pair)
            await _cleanup_client(client, timeout=self.timeouts.disconnect)
            if isinstance(exc, asyncio.CancelledError):
                self.cancelled_phase = phase
                raise
            if isinstance(exc, TimeoutError):
                raise BleConnectionError(phase, f"BLE {phase.value} timed out.") from exc
            raise BleConnectionError(phase, f"BLE {phase.value} failed.") from exc
        return BleakSession(client)

    async def disconnect(self, session: BleSession) -> None:
        task = asyncio.create_task(session.disconnect())
        try:
            await asyncio.wait_for(
                asyncio.shield(task),
                timeout=self.timeouts.disconnect,
            )
        except asyncio.CancelledError:
            self.cancelled_phase = LifecyclePhase.DISCONNECT
            await _finish_cleanup_task(task, timeout=self.timeouts.disconnect)
            raise
        except TimeoutError as exc:
            task.cancel()
            task.add_done_callback(_consume_task_result)
            raise BleConnectionError(
                LifecyclePhase.DISCONNECT,
                "BLE disconnect timed out.",
            ) from exc
        except Exception as exc:
            raise BleConnectionError(
                LifecyclePhase.DISCONNECT,
                "BLE disconnect failed.",
            ) from exc


async def _cleanup_client(client: Any, *, timeout: float) -> None:
    task = asyncio.create_task(client.disconnect())
    await _finish_cleanup_task(task, timeout=timeout)


async def _finish_cleanup_task(task: asyncio.Task[Any], *, timeout: float) -> None:
    try:
        await asyncio.wait_for(
            asyncio.shield(task),
            timeout=timeout,
        )
    except BaseException:
        if not task.done():
            task.cancel()
            task.add_done_callback(_consume_task_result)
        return


def _consume_task_result(task: asyncio.Task[Any]) -> None:
    if not task.cancelled():
        task.exception()


def _connection_failure_phase(exc: BaseException, *, pair: bool) -> LifecyclePhase:
    if pair:
        return LifecyclePhase.PREPARATION
    backend_name = " ".join(
        str(value)
        for value in (
            exc,
            getattr(exc, "dbus_error", ""),
            getattr(exc, "error_name", ""),
        )
    ).casefold()
    authentication_markers = (
        "authentication",
        "notauthorized",
        "not authorized",
        "notpaired",
        "not paired",
        "insufficient encryption",
        "access denied",
    )
    if any(marker in backend_name for marker in authentication_markers):
        return LifecyclePhase.PREPARATION
    return LifecyclePhase.CONNECT
