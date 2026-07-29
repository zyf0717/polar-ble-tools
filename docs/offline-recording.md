# Offline recording

`0.4.0` exposes offline-recording control through high-level one-operation APIs
and matching `polar-ble raw` commands.

## Inspect capabilities

Query the target before selecting a type or settings; support varies by device
and firmware.

```bash
polar-ble raw --mac-address AA:BB:CC:DD:EE:FF types
polar-ble raw --mac-address AA:BB:CC:DD:EE:FF status
polar-ble raw --mac-address AA:BB:CC:DD:EE:FF settings --type ACC --full
polar-ble raw --mac-address AA:BB:CC:DD:EE:FF disk-space
```

```python
from polar_ble_tools import (
    available_recording_types,
    recording_settings,
    recording_status,
)

types = await available_recording_types(target)
settings = await recording_settings(target, "ACC", full=True)
status = await recording_status(target)
```

## Start and stop

```bash
polar-ble raw --mac-address AA:BB:CC:DD:EE:FF \
  start --type ACC --setting sample_rate=52
polar-ble raw --mac-address AA:BB:CC:DD:EE:FF stop --type ACC
```

```python
from polar_ble_tools import start_recording, stop_recording

await start_recording(target, "ACC", {"sample_rate": 52})
# The calling application owns recording duration and scheduling.
await stop_recording(target, "ACC")
```

Each function owns one bounded BLE operation. Timed flows, scheduling,
multi-step capture protocols, and experiment orchestration belong in a separate
application layer. When one process owns both operations, call stop from a
`finally` block. `stop_recording()` waits for the selected type to become
inactive before returning.

## Triggers

Use `raw trigger get` or `offline_trigger()` to inspect the complete current
configuration. Trigger updates replace the configuration; validate the desired
types and settings first. PPI exercise-start triggers are rejected because that
combination is not supported.

## Device-state rejection

A device can reject recording start because of its current state, including
charging. `ERROR_DEVICE_IN_CHARGER` is a typed PMD response, not a BLE transport
failure. Callers can inspect `PmdResponseError.response_code`; other device
operations, including PFTP retrieval, may remain available.

After stop, the device may need time to finalize its REC file. Listing,
retrieval, and collection are separate operations.
