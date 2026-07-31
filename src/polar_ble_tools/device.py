from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field

from polar_ble_tools.ble.bleak_backend import BleakTransport, current_platform
from polar_ble_tools.ble.coordination import device_operation_guard
from polar_ble_tools.ble.lifecycle import BleLifecycle, BleLifecycleEvent
from polar_ble_tools.ble.transport import (
    BleServiceNotFound,
    BleSession,
    BleTransport,
    DevicePlatform,
    LifecyclePhase,
    LifecycleTimeouts,
)
from polar_ble_tools.inventory import InventoryError, normalize_identifier
from polar_ble_tools.polar.offline import (
    OfflineRecordingClient,
    OfflineRecordingControlClient,
)
from polar_ble_tools.polar.passive import PassiveDataClient
from polar_ble_tools.polar.pftp import PftpClient
from polar_ble_tools.polar.pmd import PmdClient
from polar_ble_tools.polar.setup import PolarSetupClient
from polar_ble_tools.polar.uuids import PFTP_SERVICE_ALIASES, PMD_SERVICE

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
    timeouts: LifecycleTimeouts | None = None,
) -> PolarDeviceSession:
    return PolarDeviceSession(
        target,
        transport_factory=transport_factory,
        timeouts=timeouts,
    )


class PolarDeviceSession:
    def __init__(
        self,
        target: PolarDeviceTarget | str,
        *,
        transport_factory: Callable[[], BleTransport] | None = None,
        lifecycle: BleLifecycle | None = None,
        timeouts: LifecycleTimeouts | None = None,
        coordinate: bool = True,
    ) -> None:
        self.target = resolve_polar_device_target(target)
        self.lifecycle = lifecycle or BleLifecycle()
        self.timeouts = timeouts or LifecycleTimeouts()
        self.operation_lock = asyncio.Lock()
        self._transport_factory = transport_factory
        self._transport: BleTransport | None = None
        self._session: BleSession | None = None
        self._services: PolarDeviceServices | None = None
        self._closed = False
        self._platform: DevicePlatform | None = None
        self._observed_services: tuple[str, ...] = ()
        self._cancelled_phase: LifecyclePhase | None = None
        self._coordinate = coordinate
        self._coordination_context: object | None = None

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

    @property
    def platform(self) -> DevicePlatform:
        return self._platform or current_platform()

    @property
    def observed_services(self) -> tuple[str, ...]:
        return self._observed_services

    async def __aenter__(self) -> PolarDeviceSession:
        if self._session is not None:
            raise PolarDeviceSessionError("Device session is already connected.")
        if self._coordinate:
            coordination = device_operation_guard(self.target.device_id or self.target.identifier)
            await coordination.__aenter__()
            self._coordination_context = coordination
        try:
            self.lifecycle.transition(
                BleLifecycleEvent.START_CONNECT,
                detail=self.target.identifier,
            )
            self._transport = (
                self._transport_factory()
                if self._transport_factory is not None
                else BleakTransport(timeouts=self.timeouts)
            )
            self._platform = getattr(self._transport, "platform", current_platform())
            self._session = await self._transport.connect(self.target.identifier)
        except BaseException as exc:
            if isinstance(exc, asyncio.CancelledError):
                self._cancelled_phase = LifecyclePhase.CONNECT
            self.lifecycle.fail(str(exc))
            self._transport = None
            await self._release_coordination()
            raise
        try:
            self.lifecycle.transition(BleLifecycleEvent.CONNECTED, detail=self.target.identifier)
            self._observed_services = await _wait_for_required_services(
                self._session,
                timeout=self.timeouts.service_readiness,
            )
            self._services = self._build_services(self._session)
            self.lifecycle.transition(
                BleLifecycleEvent.SERVICES_READY,
                detail=self.target.identifier,
            )
        except BaseException as primary:
            # connect() succeeded, so ownership exists even though service
            # construction failed; release it before surfacing the error.
            try:
                await self.aclose()
            except Exception as cleanup:
                if isinstance(primary, asyncio.CancelledError):
                    self._cancelled_phase = LifecyclePhase.SERVICE_READINESS
                else:
                    raise cleanup from primary
            raise
        self._closed = False
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        if isinstance(exc, asyncio.CancelledError):
            self._cancelled_phase = LifecyclePhase.SERVICE_READINESS
            try:
                await self.aclose()
            except Exception:
                pass
            return
        # Retaining an owned connection without reporting it is worse than
        # masking a body exception: callers need the failed cleanup signal to
        # retry or force-close deliberately.
        try:
            await self.aclose()
        except Exception as cleanup:
            if isinstance(exc, BaseException):
                raise cleanup from exc
            raise

    async def disconnect(self, _session: BleSession | None = None) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._closed or self._transport is None or self._session is None:
            await self._release_coordination()
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
            await self._release_coordination()
            raise
        self._services = None
        self._session = None
        self._transport = None
        self._closed = True
        self._observed_services = ()
        try:
            self.lifecycle.transition(
                BleLifecycleEvent.DISCONNECTED,
                detail=self.target.identifier,
            )
        finally:
            await self._release_coordination()

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

    async def _release_coordination(self) -> None:
        coordination = self._coordination_context
        if coordination is None:
            return
        self._coordination_context = None
        await coordination.__aexit__(None, None, None)


def _normalize_target_key(raw: str, *, field_name: str) -> str:
    try:
        return normalize_identifier(raw)
    except InventoryError as exc:
        raise PolarDeviceTargetError(f"Device {field_name} is empty.") from exc


def _verify_required_services(services: object) -> tuple[str, ...]:
    observed = tuple(sorted({str(item).lower() for item in services}))
    has_pmd = PMD_SERVICE in observed
    has_pftp = any(alias in observed for alias in PFTP_SERVICE_ALIASES)
    if not has_pmd or not has_pftp:
        raise BleServiceNotFound(
            LifecyclePhase.SERVICE_READINESS,
            "The selected device does not expose the required Polar PMD/PFTP services.",
        )
    return observed


async def _wait_for_required_services(
    session: BleSession,
    *,
    timeout: float,
) -> tuple[str, ...]:
    async def verify() -> tuple[str, ...]:
        await asyncio.sleep(0)
        return _verify_required_services(session.services)

    try:
        return await asyncio.wait_for(verify(), timeout=timeout)
    except TimeoutError as exc:
        raise BleServiceNotFound(
            LifecyclePhase.SERVICE_READINESS,
            "Polar PMD/PFTP service readiness timed out.",
        ) from exc
