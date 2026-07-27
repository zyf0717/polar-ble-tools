from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import Protocol

NotifyCallback = Callable[[str, bytes], None]


class BleTransportError(RuntimeError):
    """Base error for BLE backend failures."""


class BleConnectionError(BleTransportError):
    """Raised when a connection cannot be established or is lost."""


class BleServiceNotFound(BleTransportError):
    """Raised when a required BLE service or characteristic is absent."""


@dataclass(frozen=True)
class BluetoothDevice:
    mac_address: str
    name: str
    rssi: int | None = None
    details: object | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class PairingStatus:
    mac_address: str
    paired: bool
    bonded: bool
    trusted: bool
    connected: bool
    raw_info: str

    @property
    def ready(self) -> bool:
        return self.paired and self.bonded and self.trusted and self.connected

    @property
    def can_skip_pairing(self) -> bool:
        return self.paired and self.bonded and self.trusted

    @property
    def ready_for_other_actions(self) -> bool:
        """Whether another command can safely take connection ownership."""
        return self.can_skip_pairing and not self.connected


class BleSession(Protocol):
    @property
    def is_connected(self) -> bool: ...

    @property
    def services(self) -> Sequence[str]: ...

    async def disconnect(self) -> None: ...

    async def read(self, characteristic_uuid: str) -> bytes: ...

    async def write(
        self,
        characteristic_uuid: str,
        data: bytes,
        *,
        response: bool = False,
    ) -> None: ...

    async def start_notify(
        self,
        characteristic_uuid: str,
        callback: NotifyCallback,
    ) -> None: ...

    async def stop_notify(self, characteristic_uuid: str) -> None: ...


class BleTransport(Protocol):
    async def scan(
        self,
        *,
        timeout: float,
        service_uuids: Sequence[str] | None = None,
    ) -> list[BluetoothDevice]: ...

    async def connect(self, identifier: str) -> BleSession: ...

    async def disconnect(self, session: BleSession) -> None: ...


AsyncNotifyCallback = Callable[[str, bytes], Awaitable[None]]
