# Troubleshooting

## Device is not discovered

Verify that the Bluetooth controller is powered, the device is advertising, and
no phone or other host owns the connection. Retry with a longer scan:

```bash
polar-ble discover --scan-seconds 30 --name Polar
```

## Pairing does not complete

Remove only the exact stale BlueZ record, return the device to its pairing
window, and retry. Inspect current-boot logs without copying device identifiers
into public reports:

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
