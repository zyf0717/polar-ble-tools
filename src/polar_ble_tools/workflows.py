from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any, TypeVar
from weakref import WeakValueDictionary

from polar_ble_tools.ble.transport import BleTransport
from polar_ble_tools.device import (
    PolarDeviceSession,
    PolarDeviceTarget,
    open_polar_device,
    resolve_polar_device_target,
)

T = TypeVar("T")


class DeviceLockRegistry:
    """Process-shared, weakly held locks keyed by normalized device identity."""

    def __init__(self) -> None:
        self._locks: WeakValueDictionary[str, asyncio.Lock] = WeakValueDictionary()
        self._guard = asyncio.Lock()

    async def lock_for(self, device_id: str) -> asyncio.Lock:
        async with self._guard:
            lock = self._locks.get(device_id)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[device_id] = lock
            return lock


_DEVICE_LOCKS = DeviceLockRegistry()


class DeviceWorkflowRunner:
    """Serialize operations per device while ensuring session cleanup."""

    def __init__(
        self,
        *,
        transport_factory: Callable[[], BleTransport] | None = None,
        global_limiter: Any | None = None,
        lock_registry: DeviceLockRegistry | None = None,
    ) -> None:
        self.transport_factory = transport_factory
        self.global_limiter = global_limiter
        self.lock_registry = lock_registry or _DEVICE_LOCKS

    async def run(
        self,
        target: PolarDeviceTarget | str,
        workflow: Callable[[PolarDeviceSession], Awaitable[T]],
    ) -> T:
        resolved = resolve_polar_device_target(target)
        if resolved.device_id is None:  # pragma: no cover - normalization invariant
            raise ValueError("Resolved device target is missing device_id.")
        lock = await self.lock_registry.lock_for(resolved.device_id)
        async with lock:
            async with _maybe_limited(self.global_limiter):
                async with open_polar_device(
                    resolved, transport_factory=self.transport_factory
                ) as device:
                    return await workflow(device)


@asynccontextmanager
async def _maybe_limited(limiter: Any | None):
    if limiter is None:
        yield
    else:
        async with limiter:
            yield
