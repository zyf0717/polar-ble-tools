# polar-ble-tools 0.5.0

`0.5.0` is a hard Bleak-first lifecycle cutover. It replaces Linux-shaped,
MAC-specific pairing and persistent connection ownership with platform-neutral
asynchronous discovery, preparation, bounded probing, and managed sessions.

## Lifecycle

- `await scan_devices()` returns immutable identifier, platform, name, RSSI,
  and sorted service UUID records from structured advertisement data.
- `await prepare_device()` first checks existing readiness. Fresh Linux
  preparation temporarily registers an exact-target BlueZ authentication
  agent, performs one Bleak pairing attempt, disconnects, and verifies an
  agent-free reconnect.
- `await probe_device()` verifies PMD/PFTP readiness and ends disconnected.
- `async with open_polar_device(identifier)` owns longer PMD/PFTP workflows.
- Current-context native Bleak devices eliminate implicit client scans.
  Concurrent resolution requests share one scan; same-device work serializes
  and at most two distinct device sessions overlap per event loop.
- Resolution, connection, readiness, preparation, and disconnect have explicit
  budgets. Cancellation re-raises `CancelledError` after bounded cleanup.

## Breaking changes

- Use `identifier` and required `--device-identifier`; recognized MAC
  addresses and UUIDs are canonicalized and other identifiers remain opaque.
- `polar-ble prepare` replaces `polar-ble pair`.
- `polar-ble connect` is a readiness probe, not persistent ownership.
- Removed Python symbols: `BluetoothDevice`, `PairingStatus`, `PairingError`,
  `discover_devices`, `pair_device`, `connect_device`, and
  `release_device_connection`.
- Removed `polar-pair`, `polar-connect`, the `pair` subcommand,
  `--mac-address`, and the general-purpose `bluetoothctl` lifecycle.

No compatibility aliases are provided.

## Device workflows and compatibility

Raw REC, passive BPB, atomic storage, guarded cleanup, SDK schema, and local
decoder boundaries are unchanged. Loop Gen 2 and Verity Sense FTU remain
separate: Verity derives runtime time after connection and writes only time and
wear location. Pool length is rejected and deferred because no verified device
read/modify/write contract exists.

`0.5.0` remains Linux/BlueZ-first, with controlled Polar Loop Gen 2 and Polar
Verity Sense evidence. macOS and Windows workflows and physical certification
are deferred; platform-neutral identifiers and lifecycle boundaries are not
support claims.

Distributions exclude SDK source and archives, schemas, generated bindings,
decoder runtimes, recordings, captures, inventories, profiles, credentials,
identifiers, and hardware logs.
