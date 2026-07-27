# Troubleshooting

## Device is not discovered

Verify that the Bluetooth controller is powered, the device is advertising, and
no phone or other host owns the connection. Retry with a longer scan:

```bash
polar-ble discover --scan-seconds 30 --name Polar
```

## Pairing does not complete

For `org.bluez.Error.ConnectionAttemptFailed`, wait a few seconds and retry
once. If it persists, ensure no phone or other host owns the connection, then
return the device to its pairing window. Remove only the exact stale BlueZ
record if necessary. Inspect current-boot logs without copying device
identifiers into public reports:

```bash
bluetoothctl info AA:BB:CC:DD:EE:FF
journalctl -k -b
journalctl -u bluetooth -b
```

Successful durable state is paired, bonded, and trusted. A disconnected state
after pairing is normal.

## Bleak cannot reconnect

Release any BlueZ connection created by pairing before opening the async device
session. Allow a bounded settle interval after repeated pair/connect activity.
Do not run unbounded reconnect loops.

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

The `0.3.0` decoder does not support encrypted recordings or batch decoding.
Check that a renamed file
still has a supported recording name, retain the original privately, and inspect
bounded stderr diagnostics. A null timestamp can be intentional when the SDK
does not provide validated timestamp semantics.
