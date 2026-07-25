from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from polar_ble_tools.ble.transport import (
    BleConnectionError,
    BleSession,
    BleTransportError,
    BluetoothDevice,
    NotifyCallback,
)


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
            return []
        uuids: list[str] = []
        for service in services:
            uuid = getattr(service, "uuid", service)
            uuids.append(str(uuid).lower())
        return uuids

    async def disconnect(self) -> None:
        try:
            await self._client.disconnect()
        except Exception as exc:  # pragma: no cover - backend normalization
            raise BleConnectionError(f"BLE disconnect failed: {exc}") from exc

    async def read(self, characteristic_uuid: str) -> bytes:
        try:
            return bytes(await self._client.read_gatt_char(characteristic_uuid))
        except Exception as exc:  # pragma: no cover - backend normalization
            raise BleTransportError(f"BLE read failed for {characteristic_uuid}: {exc}") from exc

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
            raise BleTransportError(f"BLE write failed for {characteristic_uuid}: {exc}") from exc

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
                f"BLE start_notify failed for {characteristic_uuid}: {exc}"
            ) from exc

    async def stop_notify(self, characteristic_uuid: str) -> None:
        try:
            await self._client.stop_notify(characteristic_uuid)
        except Exception as exc:  # pragma: no cover - backend normalization
            raise BleTransportError(
                f"BLE stop_notify failed for {characteristic_uuid}: {exc}"
            ) from exc


class BleakTransport:
    def __init__(self, *, scanner_cls: Any | None = None, client_cls: Any | None = None) -> None:
        if scanner_cls is None or client_cls is None:
            from bleak import BleakClient, BleakScanner

            scanner_cls = scanner_cls or BleakScanner
            client_cls = client_cls or BleakClient
        self._scanner_cls = scanner_cls
        self._client_cls = client_cls

    async def scan(
        self,
        *,
        timeout: float,
        service_uuids: Sequence[str] | None = None,
    ) -> list[BluetoothDevice]:
        kwargs: dict[str, object] = {"timeout": timeout}
        if service_uuids is not None:
            kwargs["service_uuids"] = list(service_uuids)
        try:
            devices = await self._scanner_cls.discover(**kwargs)
        except Exception as exc:  # pragma: no cover - backend normalization
            raise BleTransportError(f"BLE scan failed: {exc}") from exc

        result: list[BluetoothDevice] = []
        for device in devices:
            result.append(
                BluetoothDevice(
                    mac_address=str(getattr(device, "address", "")),
                    name=str(getattr(device, "name", "") or ""),
                    rssi=getattr(device, "rssi", None),
                    details=getattr(device, "details", None),
                    metadata=dict(getattr(device, "metadata", {}) or {}),
                )
            )
        return result

    async def connect(self, identifier: str) -> BleSession:
        client = self._client_cls(identifier)
        try:
            await client.connect()
        except Exception as exc:
            raise BleConnectionError(f"BLE connect failed for {identifier}: {exc}") from exc
        return BleakSession(client)

    async def disconnect(self, session: BleSession) -> None:
        await session.disconnect()
