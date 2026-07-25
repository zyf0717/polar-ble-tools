from polar_ble_tools.ble.lifecycle import (
    BleLifecycle,
    BleLifecycleError,
    BleLifecycleEvent,
    BleLifecycleState,
)


def test_lifecycle_tracks_valid_connection_transfer_flow() -> None:
    lifecycle = BleLifecycle()

    lifecycle.transition(BleLifecycleEvent.START_CONNECT)
    lifecycle.transition(BleLifecycleEvent.CONNECTED)
    lifecycle.transition(BleLifecycleEvent.SERVICES_READY)
    lifecycle.transition(BleLifecycleEvent.START_TRANSFER, detail="list recordings")
    snapshot = lifecycle.transition(BleLifecycleEvent.TRANSFER_COMPLETE)

    assert snapshot.state == BleLifecycleState.SERVICES_READY
    assert [item.state for item in lifecycle.history] == [
        BleLifecycleState.IDLE,
        BleLifecycleState.CONNECTING,
        BleLifecycleState.CONNECTED,
        BleLifecycleState.SERVICES_READY,
        BleLifecycleState.TRANSFERRING,
        BleLifecycleState.SERVICES_READY,
    ]


def test_lifecycle_rejects_invalid_transition() -> None:
    lifecycle = BleLifecycle()

    try:
        lifecycle.transition(BleLifecycleEvent.START_TRANSFER)
    except BleLifecycleError as exc:
        assert "Cannot apply start_transfer from idle" in str(exc)
    else:
        raise AssertionError("Expected invalid lifecycle transition to fail.")


def test_lifecycle_tracks_connect_attempt_that_disconnects() -> None:
    lifecycle = BleLifecycle()

    lifecycle.transition(BleLifecycleEvent.START_CONNECT)
    snapshot = lifecycle.transition(BleLifecycleEvent.DISCONNECTED)

    assert snapshot.state == BleLifecycleState.DISCONNECTED
