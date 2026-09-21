# Offline recording

`0.6.0` exposes offline-recording control through high-level one-operation APIs
and matching `polar-ble raw` commands.

## Inspect capabilities

Query the target before selecting a type or settings; support varies by device
and firmware.

```bash
polar-ble raw --device-identifier AA:BB:CC:DD:EE:FF types
polar-ble raw --device-identifier AA:BB:CC:DD:EE:FF status
polar-ble raw --device-identifier AA:BB:CC:DD:EE:FF settings --type ACC --full
polar-ble raw --device-identifier AA:BB:CC:DD:EE:FF disk-space
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

## Types and settings

Canonical serialized types are `ACC`, `GYRO`, `MAGNETOMETER`, `PPG`, `PPI`,
`HR`, and `SKIN_TEMPERATURE`; availability still depends on the target.
Additional types require both a device report and a project-owned mapping.
Settings keys trim whitespace, uppercase, and replace `-` with `_`; integer
values accept Python base-zero syntax. Empty/unknown/duplicate keys, unsigned
negative values, and field-width overflow are rejected before connection when
local metadata permits.

`full=False` queries current-mode settings; `full=True` queries the full offline
set and may require SDK mode. HR/PPI settings queries are typed unsupported
unless a device-specific contract establishes otherwise. Starting without
settings sends an empty selection. Acknowledged start does not imply a REC
file has materialized; incompatible device-reported settings remain protocol
errors.

## Start and stop

```bash
polar-ble raw --device-identifier AA:BB:CC:DD:EE:FF \
  start --type ACC --setting sample_rate=52
polar-ble raw --device-identifier AA:BB:CC:DD:EE:FF stop --type ACC
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
inactive before returning; acknowledgement alone is insufficient and a bounded
poll failure raises a typed timeout.

## Triggers

Use `raw trigger get` or `offline_trigger()` to inspect the complete current
configuration. Trigger updates replace the configuration; validate the desired
types and settings first. PPI exercise-start triggers are rejected because that
combination is not supported.

Modes are `disabled`, `system-start`, and `exercise-start`. Disabled requires
no types; other modes require at least one. CLI settings apply to every selected
type; distinct settings require the Python per-type mapping. Disabled or
unsupported entries are omitted from the enabled feature map. An update result
reports normalized mode, enabled types, and `updated: true`, not recording start.

## Device-state rejection

A device can reject recording start because of its current state, including
charging. `ERROR_DEVICE_IN_CHARGER` is a typed PMD response, not a BLE transport
failure. Callers can inspect `PmdResponseError.response_code`; other device
operations, including PFTP retrieval, may remain available.

After stop, the device may need time to finalize its REC file. Listing,
retrieval, and collection are separate operations.

## Disk-space result

`fragment_size`, `total_fragments`, `free_fragments`, `total_bytes`,
`free_bytes`, and `used_bytes` are non-negative integers. Byte totals derive
from fragment counters; used space is total minus free. Missing counters,
negative derived space, or overflow beyond the protocol bound is a typed
protocol error.
