# polar-ble-tools 0.2.1

`0.2.1` updates package metadata and documentation to describe the supported
offline, device-resident collection and delayed local retrieval workflow.

## Documentation

- Reframed the package description around offline, device-resident data
  collection and delayed local retrieval.
- Expanded package keywords for offline recording, device storage, and wearable
  data collection.

## Compatibility and boundaries

Controlled hardware validation covers Polar Loop Gen 2 on Linux/BlueZ. Other
devices exposing the required PMD and PFTP services remain unconfirmed unless
listed in the [capability matrix](docs/compatibility.md).

The distribution does not include the Polar BLE SDK, SDK schema source,
generated SDK artifacts, real recordings, or a compiled decoder binary. Users
obtain and license the SDK separately.
