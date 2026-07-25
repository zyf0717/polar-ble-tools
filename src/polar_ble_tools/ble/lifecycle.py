from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping


class BleLifecycleState(StrEnum):
    IDLE = "idle"
    SCANNING = "scanning"
    PAIRING = "pairing"
    PAIRED = "paired"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    SERVICES_READY = "services_ready"
    TRANSFERRING = "transferring"
    DISCONNECTING = "disconnecting"
    DISCONNECTED = "disconnected"
    FAILED = "failed"


class BleLifecycleEvent(StrEnum):
    START_SCAN = "start_scan"
    START_PAIRING = "start_pairing"
    PAIRING_COMPLETE = "pairing_complete"
    START_CONNECT = "start_connect"
    CONNECTED = "connected"
    SERVICES_READY = "services_ready"
    START_TRANSFER = "start_transfer"
    TRANSFER_COMPLETE = "transfer_complete"
    START_DISCONNECT = "start_disconnect"
    DISCONNECTED = "disconnected"
    FAILURE = "failure"
    RESET = "reset"


class BleLifecycleError(RuntimeError):
    """Raised when a BLE lifecycle transition is invalid."""


@dataclass(frozen=True)
class BleLifecycleSnapshot:
    state: BleLifecycleState
    event: BleLifecycleEvent | None
    previous_state: BleLifecycleState | None
    detail: str | None = None


TRANSITIONS: Mapping[tuple[BleLifecycleState, BleLifecycleEvent], BleLifecycleState] = (
    MappingProxyType(
        {
            (BleLifecycleState.IDLE, BleLifecycleEvent.START_SCAN): BleLifecycleState.SCANNING,
            (
                BleLifecycleState.DISCONNECTED,
                BleLifecycleEvent.START_SCAN,
            ): BleLifecycleState.SCANNING,
            (BleLifecycleState.IDLE, BleLifecycleEvent.START_PAIRING): BleLifecycleState.PAIRING,
            (
                BleLifecycleState.SCANNING,
                BleLifecycleEvent.START_PAIRING,
            ): BleLifecycleState.PAIRING,
            (
                BleLifecycleState.DISCONNECTED,
                BleLifecycleEvent.START_PAIRING,
            ): BleLifecycleState.PAIRING,
            (
                BleLifecycleState.PAIRING,
                BleLifecycleEvent.PAIRING_COMPLETE,
            ): BleLifecycleState.PAIRED,
            (BleLifecycleState.IDLE, BleLifecycleEvent.START_CONNECT): BleLifecycleState.CONNECTING,
            (
                BleLifecycleState.PAIRED,
                BleLifecycleEvent.START_CONNECT,
            ): BleLifecycleState.CONNECTING,
            (
                BleLifecycleState.DISCONNECTED,
                BleLifecycleEvent.START_CONNECT,
            ): BleLifecycleState.CONNECTING,
            (
                BleLifecycleState.CONNECTING,
                BleLifecycleEvent.CONNECTED,
            ): BleLifecycleState.CONNECTED,
            (
                BleLifecycleState.CONNECTING,
                BleLifecycleEvent.DISCONNECTED,
            ): BleLifecycleState.DISCONNECTED,
            (
                BleLifecycleState.PAIRING,
                BleLifecycleEvent.CONNECTED,
            ): BleLifecycleState.CONNECTED,
            (
                BleLifecycleState.PAIRED,
                BleLifecycleEvent.CONNECTED,
            ): BleLifecycleState.CONNECTED,
            (
                BleLifecycleState.CONNECTED,
                BleLifecycleEvent.SERVICES_READY,
            ): BleLifecycleState.SERVICES_READY,
            (
                BleLifecycleState.CONNECTED,
                BleLifecycleEvent.START_TRANSFER,
            ): BleLifecycleState.TRANSFERRING,
            (
                BleLifecycleState.SERVICES_READY,
                BleLifecycleEvent.START_TRANSFER,
            ): BleLifecycleState.TRANSFERRING,
            (
                BleLifecycleState.TRANSFERRING,
                BleLifecycleEvent.TRANSFER_COMPLETE,
            ): BleLifecycleState.SERVICES_READY,
            (
                BleLifecycleState.DISCONNECTING,
                BleLifecycleEvent.DISCONNECTED,
            ): BleLifecycleState.DISCONNECTED,
            (
                BleLifecycleState.CONNECTED,
                BleLifecycleEvent.DISCONNECTED,
            ): BleLifecycleState.DISCONNECTED,
            (
                BleLifecycleState.SERVICES_READY,
                BleLifecycleEvent.DISCONNECTED,
            ): BleLifecycleState.DISCONNECTED,
            (
                BleLifecycleState.TRANSFERRING,
                BleLifecycleEvent.DISCONNECTED,
            ): BleLifecycleState.DISCONNECTED,
        }
    )
)


@dataclass
class BleLifecycle:
    state: BleLifecycleState = BleLifecycleState.IDLE
    history: list[BleLifecycleSnapshot] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.history.append(
            BleLifecycleSnapshot(
                state=self.state,
                event=None,
                previous_state=None,
            )
        )

    def transition(
        self,
        event: BleLifecycleEvent,
        *,
        detail: str | None = None,
    ) -> BleLifecycleSnapshot:
        previous = self.state
        if event == BleLifecycleEvent.RESET:
            next_state = BleLifecycleState.IDLE
        elif event == BleLifecycleEvent.FAILURE:
            next_state = BleLifecycleState.FAILED
        elif event == BleLifecycleEvent.START_DISCONNECT:
            if self.state in {BleLifecycleState.IDLE, BleLifecycleState.DISCONNECTED}:
                raise BleLifecycleError(f"Cannot apply {event.value} from {self.state.value}.")
            next_state = BleLifecycleState.DISCONNECTING
        else:
            try:
                next_state = TRANSITIONS[(self.state, event)]
            except KeyError as exc:
                raise BleLifecycleError(
                    f"Cannot apply {event.value} from {self.state.value}."
                ) from exc

        self.state = next_state
        snapshot = BleLifecycleSnapshot(
            state=next_state,
            event=event,
            previous_state=previous,
            detail=detail,
        )
        self.history.append(snapshot)
        return snapshot

    def fail(self, detail: str | None = None) -> BleLifecycleSnapshot:
        return self.transition(BleLifecycleEvent.FAILURE, detail=detail)

    def reset(self) -> BleLifecycleSnapshot:
        return self.transition(BleLifecycleEvent.RESET)
