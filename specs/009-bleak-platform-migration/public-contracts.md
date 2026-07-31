# Public contracts

The exact import layout is finalized with the reviewed decision matrix. The
`0.5.0` contract follows the semantics below and does not preserve `0.4.x`
argument names or persistent connection ownership.

## Device identity and discovery

`identifier` is the canonical opaque target key. CLI commands use
`--device-identifier`; inventory and authorization APIs store allowed
identifiers without assuming that every platform exposes a MAC address.

The canonical discovered-device model is immutable and contains:

```text
identifier
platform
name
rssi
service_uuids
```

Advertisement payloads, native backend details, and `BLEDevice` instances are
not part of the public model.

The canonical discovery API is asynchronous:

```python
await scan_devices(timeout=10.0, name_substring="Polar")
```

Discovery is read-only. It neither prepares nor connects a device.

## Preparation and probing

The canonical preparation operation is asynchronous and may pair only when the
selected platform/device workflow requires it:

```python
await prepare_device(identifier)
```

Its immutable result contains:

```text
identifier
platform
outcome                 ready | already_ready | not_required
readiness_verified
reconnect_persistence   verified | not_required | not_tested
final_connected
```

A successful preparation ends disconnected. Backend-specific pairing, bonding,
or trust observations may appear in private diagnostics but are not portable
public success fields.

The canonical connection command is a bounded readiness probe:

```python
await probe_device(identifier)
```

The probe connects, verifies required Polar services, reports readiness and
observed service UUIDs, and disconnects before returning. A successful result
has `final_connected == false`.

Callers that need multiple operations in one connection use the managed
session:

```python
async with open_polar_device(identifier) as device:
    ...
```

## Device-specific FTU

`apply_ftu(identifier, profile)` selects an explicit setup path from the
validated profile family. Loop Gen 2 writes its physical profile and
user-identifier contract. Verity Sense derives current timezone-aware host time
after connection, writes system/local time, and patches wear location through
`UDEVSET.BPB`. The Verity profile contains only device family and wear
location; it rejects Loop fields and unverified pool-length input.

## CLI

`polar-ble` remains canonical:

```text
polar-ble discover
polar-ble prepare --device-identifier IDENTIFIER
polar-ble connect --device-identifier IDENTIFIER
polar-ble raw --device-identifier IDENTIFIER ...
polar-ble passive --device-identifier IDENTIFIER ...
polar-ble ftu --device-identifier IDENTIFIER ...
```

`connect` performs the bounded readiness probe; it does not leave a connection
owned by the OS. Standalone `polar-connect` and `polar-pair` entry points are
removed. Success output remains deterministic JSON and errors use stderr.

## Errors

Public lifecycle failures retain a stable category and phase:

```text
discovery
authorization
resolution
preparation
connect
service_readiness
disconnect
cancelled
unsupported
```

Backend exceptions remain chained for local diagnostics. Public messages do
not include advertisement payloads, native backend objects, inventory content,
or captures.

## Breaking-change policy

`0.5.0` removes `mac_address`, `--mac-address`, synchronous discovery,
Linux-shaped `PairingStatus`, persistent `connect_device()`, and
`release_device_connection()`. Changelog, release notes, CLI/Python references,
and architecture documentation list every accepted removal. Later `0.5.x`
releases harden this contract without another avoidable public redesign.
