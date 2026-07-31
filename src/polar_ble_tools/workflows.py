from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any, TypeVar

from polar_ble_tools.ble.coordination import (
    DeviceLockRegistry,
    device_operation_guard,
)
from polar_ble_tools.ble.transport import BleTransport, LifecycleTimeouts
from polar_ble_tools.device import (
    PolarDeviceSession,
    PolarDeviceTarget,
    resolve_polar_device_target,
)

T = TypeVar("T")


class DeviceWorkflowRunner:
    """Serialize operations per device while ensuring session cleanup."""

    def __init__(
        self,
        *,
        transport_factory: Callable[[], BleTransport] | None = None,
        global_limiter: Any | None = None,
        lock_registry: DeviceLockRegistry | None = None,
        timeouts: LifecycleTimeouts | None = None,
    ) -> None:
        self.transport_factory = transport_factory
        self.global_limiter = global_limiter
        self.lock_registry = lock_registry
        self.timeouts = timeouts

    @asynccontextmanager
    async def guard(self, target: PolarDeviceTarget | str):
        """Serialize and bound one complete device-facing workflow."""

        resolved = resolve_polar_device_target(target)
        if resolved.device_id is None:  # pragma: no cover - normalization invariant
            raise ValueError("Resolved device target is missing device_id.")
        async with device_operation_guard(
            resolved.device_id,
            lock_registry=self.lock_registry,
            limiter=self.global_limiter,
        ):
            yield resolved

    async def run(
        self,
        target: PolarDeviceTarget | str,
        workflow: Callable[[PolarDeviceSession], Awaitable[T]],
    ) -> T:
        async with self.guard(target) as resolved:
            async with PolarDeviceSession(
                resolved,
                transport_factory=self.transport_factory,
                timeouts=self.timeouts,
                coordinate=False,
            ) as device:
                return await workflow(device)
