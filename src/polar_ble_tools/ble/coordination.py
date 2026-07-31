from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any
from weakref import WeakKeyDictionary, WeakValueDictionary

from polar_ble_tools.inventory import identifier_key


class DeviceLockRegistry:
    """Process-shared, weakly held locks keyed by normalized device identity."""

    def __init__(self) -> None:
        self._locks: WeakValueDictionary[str, asyncio.Lock] = WeakValueDictionary()
        self._guard = asyncio.Lock()

    async def lock_for(self, identifier: str) -> asyncio.Lock:
        key = identifier_key(identifier)
        async with self._guard:
            lock = self._locks.get(key)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[key] = lock
            return lock


class DeviceConcurrencyRegistry:
    """Per-event-loop bound for independent managed device sessions."""

    def __init__(self, limit: int = 2) -> None:
        self.limit = limit
        self._limiters: WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore] = (
            WeakKeyDictionary()
        )

    def limiter(self) -> asyncio.Semaphore:
        loop = asyncio.get_running_loop()
        limiter = self._limiters.get(loop)
        if limiter is None:
            limiter = asyncio.Semaphore(self.limit)
            self._limiters[loop] = limiter
        return limiter


DEVICE_LOCKS = DeviceLockRegistry()
DEVICE_LIMITERS = DeviceConcurrencyRegistry()


@asynccontextmanager
async def device_operation_guard(
    identifier: str,
    *,
    lock_registry: DeviceLockRegistry | None = None,
    limiter: Any | None = None,
):
    selected_locks = lock_registry if lock_registry is not None else DEVICE_LOCKS
    lock = await selected_locks.lock_for(identifier)
    async with lock:
        selected_limiter = limiter if limiter is not None else DEVICE_LIMITERS.limiter()
        async with selected_limiter:
            yield
