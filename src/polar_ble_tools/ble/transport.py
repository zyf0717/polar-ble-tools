from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

NotifyCallback = Callable[[str, bytes], None]
AsyncNotifyCallback = Callable[[str, bytes], Awaitable[None]]


class DevicePlatform(StrEnum):
    LINUX = "linux"
    MACOS = "macos"
    WINDOWS = "windows"


class PreparationOutcome(StrEnum):
    READY = "ready"
    ALREADY_READY = "already_ready"
    NOT_REQUIRED = "not_required"


class ReconnectPersistence(StrEnum):
    VERIFIED = "verified"
    NOT_REQUIRED = "not_required"
    NOT_TESTED = "not_tested"


class LifecyclePhase(StrEnum):
    DISCOVERY = "discovery"
    AUTHORIZATION = "authorization"
    RESOLUTION = "resolution"
    PREPARATION = "preparation"
    CONNECT = "connect"
    SERVICE_READINESS = "service_readiness"
    DISCONNECT = "disconnect"
    CANCELLED = "cancelled"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class LifecycleTimeouts:
    discovery: float = 10.0
    resolution: float = 10.0
    preparation: float = 45.0
    connect: float = 30.0
    service_readiness: float = 10.0
    disconnect: float = 10.0

    def __post_init__(self) -> None:
        for field_name in (
            "discovery",
            "resolution",
            "preparation",
            "connect",
            "service_readiness",
            "disconnect",
        ):
            if getattr(self, field_name) <= 0:
                raise ValueError(f"{field_name} timeout must be greater than zero.")


@dataclass(frozen=True)
class DiscoveredDevice:
    identifier: str
    platform: DevicePlatform
    name: str | None
    rssi: int | None
    service_uuids: tuple[str, ...]

    def to_jsonable(self) -> dict[str, object]:
        return {
            "identifier": self.identifier,
            "platform": self.platform.value,
            "name": self.name,
            "rssi": self.rssi,
            "service_uuids": list(self.service_uuids),
        }


@dataclass(frozen=True)
class PreparationResult:
    identifier: str
    platform: DevicePlatform
    outcome: PreparationOutcome
    readiness_verified: bool
    reconnect_persistence: ReconnectPersistence
    final_connected: bool

    def to_jsonable(self) -> dict[str, object]:
        return {
            "identifier": self.identifier,
            "platform": self.platform.value,
            "outcome": self.outcome.value,
            "readiness_verified": self.readiness_verified,
            "reconnect_persistence": self.reconnect_persistence.value,
            "final_connected": self.final_connected,
        }


@dataclass(frozen=True)
class ProbeResult:
    identifier: str
    platform: DevicePlatform
    readiness_verified: bool
    service_uuids: tuple[str, ...]
    final_connected: bool

    def to_jsonable(self) -> dict[str, object]:
        return {
            "identifier": self.identifier,
            "platform": self.platform.value,
            "readiness_verified": self.readiness_verified,
            "service_uuids": list(self.service_uuids),
            "final_connected": self.final_connected,
        }


class DeviceLifecycleError(RuntimeError):
    """Stable lifecycle failure with a redacted public phase."""

    def __init__(
        self,
        phase: LifecyclePhase,
        message: str,
    ) -> None:
        self.phase = phase
        super().__init__(message)


class BleTransportError(DeviceLifecycleError):
    """Base error for BLE backend failures."""


class BleConnectionError(BleTransportError):
    """Raised when a connection cannot be established or is lost."""


class BleServiceNotFound(BleTransportError):
    """Raised when a required BLE service or characteristic is absent."""


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
        name_substring: str | None = None,
    ) -> tuple[DiscoveredDevice, ...]: ...

    async def connect(self, identifier: str, *, pair: bool = False) -> BleSession: ...

    async def disconnect(self, session: BleSession) -> None: ...
