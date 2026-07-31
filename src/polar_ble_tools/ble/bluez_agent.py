from __future__ import annotations

import asyncio
from types import TracebackType
from typing import Any
from weakref import WeakKeyDictionary

from dbus_fast import BusType, DBusError
from dbus_fast.aio import MessageBus
from dbus_fast.service import ServiceInterface, method

from polar_ble_tools.ble.transport import DeviceLifecycleError, LifecyclePhase
from polar_ble_tools.inventory import normalize_identifier
from polar_ble_tools.polar.uuids import PFTP_SERVICE_ALIASES, PMD_SERVICE

BLUEZ_SERVICE = "org.bluez"
BLUEZ_MANAGER_PATH = "/org/bluez"
BLUEZ_AGENT_MANAGER = "org.bluez.AgentManager1"
AGENT_INTERFACE = "org.bluez.Agent1"
AGENT_PATH = "/org/polar_ble_tools/agent"
AGENT_CAPABILITY = "KeyboardDisplay"
REJECTED_ERROR = "org.bluez.Error.Rejected"
ALLOWED_SERVICE_UUIDS = frozenset({PMD_SERVICE, *PFTP_SERVICE_ALIASES})
_AGENT_LOCKS: WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Lock] = WeakKeyDictionary()


def _agent_lock() -> asyncio.Lock:
    loop = asyncio.get_running_loop()
    lock = _AGENT_LOCKS.get(loop)
    if lock is None:
        lock = asyncio.Lock()
        _AGENT_LOCKS[loop] = lock
    return lock


class TargetBoundAgent(ServiceInterface):
    """Accept only supported callbacks for one explicitly selected device."""

    def __init__(self, identifier: str) -> None:
        super().__init__(AGENT_INTERFACE)
        normalized = normalize_identifier(identifier)
        self._device_suffix = "/dev_" + normalized.replace(":", "_")
        self.released = False
        self.cancelled = False

    def _require_target(self, device: str) -> None:
        if not device.upper().endswith(self._device_suffix.upper()):
            raise DBusError(REJECTED_ERROR, "Authentication request target was not selected.")

    @method(name="Release")
    def release(self) -> "":
        self.released = True

    @method(name="RequestPinCode")
    def request_pin_code(self, device: "o") -> "s":
        self._require_target(device)
        raise DBusError(REJECTED_ERROR, "PIN entry is unsupported.")

    @method(name="DisplayPinCode")
    def display_pin_code(self, device: "o", pincode: "s") -> "":
        del pincode
        self._require_target(device)

    @method(name="RequestPasskey")
    def request_passkey(self, device: "o") -> "u":
        self._require_target(device)
        raise DBusError(REJECTED_ERROR, "Passkey entry is unsupported.")

    @method(name="DisplayPasskey")
    def display_passkey(self, device: "o", passkey: "u", entered: "q") -> "":
        del passkey, entered
        self._require_target(device)

    @method(name="RequestConfirmation")
    def request_confirmation(self, device: "o", passkey: "u") -> "":
        del passkey
        self._require_target(device)

    @method(name="RequestAuthorization")
    def request_authorization(self, device: "o") -> "":
        self._require_target(device)

    @method(name="AuthorizeService")
    def authorize_service(self, device: "o", uuid: "s") -> "":
        self._require_target(device)
        if uuid.lower() not in ALLOWED_SERVICE_UUIDS:
            raise DBusError(REJECTED_ERROR, "Service authorization is unsupported.")

    @method(name="Cancel")
    def cancel(self) -> "":
        self.cancelled = True


class LinuxAuthenticationAgent:
    def __init__(
        self,
        identifier: str,
        *,
        bus_factory: Any = MessageBus,
        timeout: float = 10.0,
    ) -> None:
        self.identifier = normalize_identifier(identifier)
        self._bus_factory = bus_factory
        self._bus: Any | None = None
        self._manager: Any | None = None
        self._registered = False
        self._registration_attempted = False
        self._timeout = timeout
        self.agent = TargetBoundAgent(self.identifier)
        self._lock: asyncio.Lock | None = None

    async def __aenter__(self) -> LinuxAuthenticationAgent:
        self._lock = _agent_lock()
        await self._lock.acquire()
        try:
            self._bus = await asyncio.wait_for(
                self._bus_factory(bus_type=BusType.SYSTEM).connect(),
                timeout=self._timeout,
            )
            self._bus.export(AGENT_PATH, self.agent)
            introspection = await asyncio.wait_for(
                self._bus.introspect(BLUEZ_SERVICE, BLUEZ_MANAGER_PATH),
                timeout=self._timeout,
            )
            proxy = self._bus.get_proxy_object(
                BLUEZ_SERVICE,
                BLUEZ_MANAGER_PATH,
                introspection,
            )
            self._manager = proxy.get_interface(BLUEZ_AGENT_MANAGER)
            self._registration_attempted = True
            await asyncio.wait_for(
                self._manager.call_register_agent(AGENT_PATH, AGENT_CAPABILITY),
                timeout=self._timeout,
            )
            self._registered = True
            await asyncio.wait_for(
                self._manager.call_request_default_agent(AGENT_PATH),
                timeout=self._timeout,
            )
        except BaseException as exc:
            try:
                await self._cleanup()
            finally:
                self._release_lock()
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            if isinstance(exc, Exception):
                raise DeviceLifecycleError(
                    LifecyclePhase.PREPARATION,
                    "Linux authentication-agent registration failed.",
                ) from exc
            raise
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback
        try:
            await self._cleanup()
        finally:
            self._release_lock()

    async def _cleanup(self) -> None:
        manager = self._manager
        bus = self._bus
        if self._registration_attempted and manager is not None:
            try:
                await asyncio.wait_for(
                    manager.call_unregister_agent(AGENT_PATH),
                    timeout=self._timeout,
                )
            except Exception:
                pass
        self._registered = False
        self._registration_attempted = False
        if bus is not None:
            try:
                bus.unexport(AGENT_PATH, self.agent)
            except Exception:
                pass
            bus.disconnect()
        self._manager = None
        self._bus = None

    def _release_lock(self) -> None:
        if self._lock is not None and self._lock.locked():
            self._lock.release()
        self._lock = None
