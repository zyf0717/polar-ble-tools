from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from pathlib import Path
from typing import Any

from polar_ble_tools.ble.bleak_backend import BleakTransport, current_platform
from polar_ble_tools.ble.transport import (
    BleServiceNotFound,
    BleSession,
    BleTransport,
    DeviceLifecycleError,
    DevicePlatform,
    DiscoveredDevice,
    LifecyclePhase,
    LifecycleTimeouts,
    PreparationOutcome,
    PreparationResult,
    ProbeResult,
    ReconnectPersistence,
)
from polar_ble_tools.device import PolarDeviceSession
from polar_ble_tools.inventory import InventoryError, require_authorized_identifier
from polar_ble_tools.polar.uuids import PFTP_SERVICE_ALIASES, PMD_SERVICE
from polar_ble_tools.workflows import DeviceWorkflowRunner

TransportFactory = Callable[[], BleTransport]
AgentFactory = Callable[[str], AbstractAsyncContextManager[Any]]


async def scan_devices(
    timeout: float = 10.0,
    name_substring: str | None = None,
    *,
    transport_factory: TransportFactory | None = None,
) -> tuple[DiscoveredDevice, ...]:
    if timeout <= 0:
        raise ValueError("timeout must be greater than zero.")
    transport = transport_factory() if transport_factory else BleakTransport()
    return await transport.scan(timeout=timeout, name_substring=name_substring)


async def probe_device(
    identifier: str,
    *,
    devices_file: str | Path | None = None,
    timeouts: LifecycleTimeouts | None = None,
    transport_factory: TransportFactory | None = None,
) -> ProbeResult:
    normalized = _authorized(identifier, devices_file)
    runner = DeviceWorkflowRunner(
        transport_factory=transport_factory,
        timeouts=timeouts,
    )
    platform, observed_services = await runner.run(normalized, _probe_ready_session)
    return ProbeResult(
        identifier=normalized,
        platform=platform,
        readiness_verified=True,
        service_uuids=observed_services,
        final_connected=False,
    )


async def prepare_device(
    identifier: str,
    *,
    devices_file: str | Path | None = None,
    timeouts: LifecycleTimeouts | None = None,
    transport_factory: TransportFactory | None = None,
    agent_factory: AgentFactory | None = None,
) -> PreparationResult:
    normalized = _authorized(identifier, devices_file)
    selected_timeouts = timeouts or LifecycleTimeouts()
    runner = DeviceWorkflowRunner(
        transport_factory=transport_factory,
        timeouts=selected_timeouts,
    )
    async with runner.guard(normalized):
        try:
            platform, _ = await _probe_once(
                normalized,
                timeouts=selected_timeouts,
                transport_factory=transport_factory,
            )
        except DeviceLifecycleError as exc:
            if exc.phase is not LifecyclePhase.PREPARATION:
                raise
        else:
            return PreparationResult(
                identifier=normalized,
                platform=platform,
                outcome=PreparationOutcome.ALREADY_READY,
                readiness_verified=True,
                reconnect_persistence=ReconnectPersistence.VERIFIED,
                final_connected=False,
            )

        platform = current_platform()
        if platform is DevicePlatform.LINUX:
            if agent_factory is None:
                from polar_ble_tools.ble.bluez_agent import LinuxAuthenticationAgent

                agent_factory = LinuxAuthenticationAgent
            async with agent_factory(normalized):
                await _pair_once(
                    normalized,
                    timeouts=selected_timeouts,
                    transport_factory=transport_factory,
                )
        else:
            await _pair_once(
                normalized,
                timeouts=selected_timeouts,
                transport_factory=transport_factory,
            )

        reconnect_platform, _ = await _probe_once(
            normalized,
            timeouts=selected_timeouts,
            transport_factory=transport_factory,
        )
    return PreparationResult(
        identifier=normalized,
        platform=reconnect_platform,
        outcome=PreparationOutcome.READY,
        readiness_verified=True,
        reconnect_persistence=ReconnectPersistence.VERIFIED,
        final_connected=False,
    )


async def _probe_ready_session(device: Any) -> tuple[DevicePlatform, tuple[str, ...]]:
    return device.platform, device.observed_services


async def _probe_once(
    identifier: str,
    *,
    timeouts: LifecycleTimeouts,
    transport_factory: TransportFactory | None,
) -> tuple[DevicePlatform, tuple[str, ...]]:
    async with PolarDeviceSession(
        identifier,
        transport_factory=transport_factory,
        timeouts=timeouts,
        coordinate=False,
    ) as device:
        return await _probe_ready_session(device)


async def _pair_once(
    identifier: str,
    *,
    timeouts: LifecycleTimeouts,
    transport_factory: TransportFactory | None,
) -> None:
    transport = transport_factory() if transport_factory else BleakTransport(timeouts=timeouts)
    session: BleSession | None = None
    cancelled = False
    try:
        session = await asyncio.wait_for(
            transport.connect(identifier, pair=True),
            timeout=timeouts.preparation,
        )
        _required_services(session.services)
    except TimeoutError as exc:
        raise DeviceLifecycleError(
            LifecyclePhase.PREPARATION,
            "BLE preparation timed out.",
        ) from exc
    except asyncio.CancelledError:
        cancelled = True
        raise
    finally:
        if session is not None:
            try:
                await transport.disconnect(session)
            except Exception:
                if not cancelled:
                    raise


def _required_services(services: object) -> tuple[str, ...]:
    observed = tuple(sorted({str(item).lower() for item in services}))
    if PMD_SERVICE not in observed or not any(item in observed for item in PFTP_SERVICE_ALIASES):
        raise BleServiceNotFound(
            LifecyclePhase.SERVICE_READINESS,
            "The selected device does not expose the required Polar PMD/PFTP services.",
        )
    return observed


def _authorized(identifier: str, devices_file: str | Path | None) -> str:
    try:
        return require_authorized_identifier(identifier, devices_file)
    except InventoryError as exc:
        raise DeviceLifecycleError(
            LifecyclePhase.AUTHORIZATION,
            str(exc),
        ) from exc
