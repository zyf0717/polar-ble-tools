from __future__ import annotations

import asyncio
import re
from collections.abc import Callable
from dataclasses import dataclass, field

from polar_ble_tools.ble.bleak_backend import BleakTransport
from polar_ble_tools.ble.lifecycle import BleLifecycle, BleLifecycleEvent
from polar_ble_tools.ble.transport import BleSession, BleTransport
from polar_ble_tools.polar.offline import (
    OfflineRecordingClient,
    OfflineRecordingControlClient,
)
from polar_ble_tools.polar.passive import PassiveDataClient
from polar_ble_tools.polar.pftp import PftpClient
from polar_ble_tools.polar.pmd import PmdClient
from polar_ble_tools.polar.setup import PolarSetupClient

MAC_KEY_RE = re.compile(r"^[0-9A-Fa-f:-]+$")

__all__ = [
    "PolarDeviceServices",
    "PolarDeviceSession",
    "PolarDeviceSessionError",
    "PolarDeviceTarget",
    "PolarDeviceTargetError",
    "open_polar_device",
    "resolve_polar_device_target",
]


class PolarDeviceTargetError(ValueError):
    """Raised when a device target cannot be normalized."""


class PolarDeviceSessionError(RuntimeError):
    """Raised when a managed device session is used outside its lifecycle."""


@dataclass(frozen=True)
class PolarDeviceTarget:
    identifier: str
    device_id: str | None = None
    name: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class PolarDeviceServices:
    pftp: PftpClient
    pmd: PmdClient
    passive: PassiveDataClient
    offline: OfflineRecordingClient
    offline_control: OfflineRecordingControlClient
    setup: PolarSetupClient


def resolve_polar_device_target(target: PolarDeviceTarget | str) -> PolarDeviceTarget:
    if isinstance(target, str):
        target = PolarDeviceTarget(identifier=target)
    identifier = _normalize_target_key(target.identifier, field_name="identifier")
    device_id_source = target.device_id if target.device_id is not None else identifier
    return PolarDeviceTarget(
        identifier=identifier,
        device_id=_normalize_target_key(device_id_source, field_name="device_id"),
        name=target.name,
        metadata=dict(target.metadata),
    )


def open_polar_device(
    target: PolarDeviceTarget | str,
    *,
    transport_factory: Callable[[], BleTransport] | None = None,
) -> PolarDeviceSession:
    return PolarDeviceSession(target, transport_factory=transport_factory)


class PolarDeviceSession:
    def __init__(
        self,
        target: PolarDeviceTarget | str,
        *,
        transport_factory: Callable[[], BleTransport] | None = None,
        lifecycle: BleLifecycle | None = None,
    ) -> None:
        self.target = resolve_polar_device_target(target)
        self.lifecycle = lifecycle or BleLifecycle()
        self.operation_lock = asyncio.Lock()
        self._transport_factory = transport_factory or BleakTransport
        self._transport: BleTransport | None = None
        self._session: BleSession | None = None
        self._services: PolarDeviceServices | None = None
        self._closed = False

    @property
    def transport(self) -> BleTransport:
        if self._transport is None:
            raise PolarDeviceSessionError("Device session is not connected.")
        return self._transport

    @property
    def session(self) -> BleSession:
        if self._session is None:
            raise PolarDeviceSessionError("Device session is not connected.")
        return self._session

    @property
    def services(self) -> PolarDeviceServices:
        if self._services is None:
            raise PolarDeviceSessionError("Device services are not ready.")
        return self._services

    async def __aenter__(self) -> PolarDeviceSession:
        if self._session is not None:
            raise PolarDeviceSessionError("Device session is already connected.")
        self.lifecycle.transition(
            BleLifecycleEvent.START_CONNECT,
            detail=self.target.identifier,
        )
        self._transport = self._transport_factory()
        try:
            self._session = await self._transport.connect(self.target.identifier)
        except Exception as exc:
            self.lifecycle.fail(str(exc))
            self._transport = None
            raise
        try:
            self.lifecycle.transition(BleLifecycleEvent.CONNECTED, detail=self.target.identifier)
            self._services = self._build_services(self._session)
            self.lifecycle.transition(
                BleLifecycleEvent.SERVICES_READY,
                detail=self.target.identifier,
            )
        except Exception as exc:
            # connect() succeeded, so ownership exists even though service
            # construction failed; release it before surfacing the error.
            try:
                await self.aclose()
            except Exception:
                pass
            raise exc
        self._closed = False
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        # Retaining an owned connection without reporting it is worse than
        # masking a body exception: callers need the failed cleanup signal to
        # retry or force-close deliberately.
        await self.aclose()

    async def disconnect(self, _session: BleSession | None = None) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._closed or self._transport is None or self._session is None:
            return
        transport = self._transport
        session = self._session
        self.lifecycle.transition(
            BleLifecycleEvent.START_DISCONNECT,
            detail=self.target.identifier,
        )
        try:
            await transport.disconnect(session)
        except Exception as exc:
            self.lifecycle.fail(str(exc))
            raise
        self._services = None
        self._session = None
        self._transport = None
        self._closed = True
        self.lifecycle.transition(
            BleLifecycleEvent.DISCONNECTED,
            detail=self.target.identifier,
        )

    def _build_services(self, session: BleSession) -> PolarDeviceServices:
        pftp = PftpClient(session)
        pmd = PmdClient(session)
        return PolarDeviceServices(
            pftp=pftp,
            pmd=pmd,
            passive=PassiveDataClient(pftp),
            offline=OfflineRecordingClient(pftp, lifecycle=self.lifecycle),
            offline_control=OfflineRecordingControlClient(pmd),
            setup=PolarSetupClient(pftp),
        )


def _normalize_target_key(raw: str, *, field_name: str) -> str:
    value = raw.strip()
    if not value:
        raise PolarDeviceTargetError(f"Device {field_name} is empty.")
    compact = value.replace(":", "").replace("-", "")
    if len(compact) == 12 and MAC_KEY_RE.fullmatch(value):
        upper = compact.upper()
        return ":".join(upper[index : index + 2] for index in range(0, 12, 2))
    return value
