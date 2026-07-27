# polar-ble-tools 0.3.2

`0.3.2` is an urgent Linux/BlueZ pairing and connection-ownership release.

## Fixed

- `polar-ble pair` always uses live scan observations while retaining an
  existing explicit BlueZ bond as a fallback for direct connection
  verification when a device is not observed during the scan.
- Pairing now releases its temporary verification connection before returning.
  The final status explicitly reports when the device is ready for another
  action to own the connection.

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
