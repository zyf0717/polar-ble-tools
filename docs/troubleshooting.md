# Troubleshooting

## Device is not discovered

Verify that the Bluetooth controller is powered, the device is advertising, and
no phone or other host owns the connection. Retry with a longer scan:

```bash
polar-ble discover --timeout 30 --name Polar
```

## Preparation does not complete

`polar-ble prepare` performs no generic retry. If a bounded attempt fails,
ensure no phone or other host owns the connection, return the device to its
pairing window, and run the isolated command once more. The temporary Linux
authentication agent accepts only the exact selected device and unregisters
after every outcome. The package never removes a bond or changes adapter
policy. Inspect current-boot logs without copying device identifiers into
public reports:

```bash
journalctl -k -b
journalctl -u bluetooth -b
```

Successful preparation reports verified readiness and reconnect persistence.
A disconnected final state is required.

## Bleak cannot reconnect

`polar-ble connect` is a bounded readiness probe and finishes disconnected.
Library callers that need multiple operations must use
`async with open_polar_device(identifier)`. Do not run unbounded reconnect
loops.

A reconnect timeout can occur while BlueZ is processing
`org.bluez.Device1.Disconnect`, before the next connection attempt begins.
Retain the timeout phase in the private diagnostic record, allow a bounded
settle interval, and retry the isolated probe. Do not remove a durable host
record solely because disconnect teardown exceeded one attempt timeout.

## Schema-backed command fails

Check readiness and verify the active cache:

```bash
polar-ble doctor
polar-ble sdk status
polar-ble sdk verify
```

If the compiler is missing, install `polar-ble-tools[sdk]`. If source discovery,
generation, or verification fails, the CLI reports a concise setup error and
keeps the prior active cache. Use `sdk remove` only for the exact reviewed
revision, or `--all` when intentionally clearing the entire local SDK cache.

## Retrieved file fails verification

Do not delete the device copy. Preserve the manifest and local file privately,
collect again, and compare the reported device size. Cleanup remains blocked
until size and SHA-256 verification succeeds.

If cleanup reports selected entries but `dry_run=0` and only blocked outcomes,
confirm that collection and cleanup use the same `--root`. This result shows
that the guard prevented deletion; it is not evidence that an eligible cleanup
candidate completed a dry run.

## Recording start is rejected by device state

Treat `ERROR_DEVICE_IN_CHARGER` as a typed PMD device-state response rather than
a dropped BLE link. Stop charging or change the device state before retrying
recording start. Listing or retrieving existing files may still work, so do not
disable PFTP collection solely because recording start was rejected.

## REC decoder is unavailable

Run `polar-ble rec status` and `polar-ble sdk decoder verify`. A changed or
missing JDK, launcher, runtime JAR, manifest, platform mismatch, or failed
handshake makes the decoder unavailable. Rebuild it; removal is limited to an
exact full commit SHA.

## REC decode fails

The `0.5.0` decoder does not support encrypted recordings or batch decoding.
Check that a renamed file
still has a supported recording name, retain the original privately, and inspect
bounded stderr diagnostics. A null timestamp can be intentional when the SDK
does not provide validated timestamp semantics.
