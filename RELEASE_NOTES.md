# polar-ble-tools 0.3.1

`0.3.1` is an urgent Linux/BlueZ discovery-correctness release.

## Fixed

- `polar-ble discover` now reports only device observations received during its
  active scan. Cached BlueZ device records are excluded, preventing stale
  paired devices from being reported as currently discoverable.
- BlueZ connection-attempt failures now provide concise bounded-retry and
  troubleshooting guidance.

## Compatibility and boundaries

The supported devices remain Polar Loop Gen 2 and Polar Verity Sense, limited
to the operations in the [compatibility matrix](docs/compatibility.md).
This release does not add device, protocol, or REC-decoder compatibility.

The distribution includes no Polar SDK source, generated SDK artifacts, real
recordings, device inventories, profiles, credentials, or hardware logs.

## Documentation

- [Configuration and CLI](https://github.com/zyf0717/polar-ble-tools/blob/main/docs/configuration.md)
- [Troubleshooting](https://github.com/zyf0717/polar-ble-tools/blob/main/docs/troubleshooting.md)
- [Compatibility](https://github.com/zyf0717/polar-ble-tools/blob/main/docs/compatibility.md)
- [Release process](https://github.com/zyf0717/polar-ble-tools/blob/main/docs/releasing.md)
