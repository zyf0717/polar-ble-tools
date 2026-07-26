# polar-ble-tools

Independent Python tools for working with supported Polar wearable devices over
Bluetooth Low Energy.

> `polar-ble-tools` is an unofficial community project. It is not affiliated
> with, endorsed by, sponsored by, or maintained by Polar Electro Oy.

## Capabilities

- discover, pair, and connect devices through Linux BlueZ;
- issue PMD commands and manage offline recording;
- use PFTP to list, retrieve, and manage device files;
- retrieve raw `.REC` recordings with SHA-256 manifests and guarded cleanup;
- retrieve passive `.BPB` files and decode supported data with local schemas;
- validate and apply first-time-use (FTU) data;
- generate and verify optional local schemas from a separately obtained SDK;
- optionally decode supported `.REC` files to validated JSONL using a locally built SDK sidecar.

## Installation

Device operations require Linux, BlueZ, and `bluetoothctl`. Python 3.11 or
newer is supported.

```bash
python -m pip install polar-ble-tools
polar-ble --help
```

Install the optional schema compiler only for SDK-assisted FTU encoding and BPB
decoding:

```bash
python -m pip install "polar-ble-tools[sdk]"
polar-ble sdk install --accept-license
```

## Quick start

Discover and pair a device:

```bash
polar-ble discover --scan-seconds 15 --name Polar
polar-ble pair --mac-address AA:BB:CC:DD:EE:FF --scan-seconds 15
```

List and collect raw recordings:

```bash
polar-ble raw --mac-address AA:BB:CC:DD:EE:FF list
polar-ble raw --mac-address AA:BB:CC:DD:EE:FF collect
```

Review a cleanup without deleting device files:

```bash
polar-ble raw --mac-address AA:BB:CC:DD:EE:FF cleanup --all --dry-run
```

See [device setup](docs/device-setup.md), [offline recording](docs/offline-recording.md),
and [raw retrieval](docs/raw-file-retrieval.md) before performing device
mutations.

## Compatibility

Controlled hardware validation covers Polar Loop Gen 2 on Linux/BlueZ. Other
devices exposing the required PMD and PFTP services may work but are not
confirmed for this release. See [compatibility](docs/compatibility.md) for the
verified capability matrix and limitations.

## Optional SDK-assisted functionality

The package does not distribute the Polar BLE SDK, Polar SDK schema files, or
artefacts generated from those files. Optional SDK-assisted functionality uses
an SDK copy separately obtained and licensed by the user.

SDK download, inspection, generation, verification, activation, and removal are
explicit `polar-ble sdk` commands. Package installation and import never perform
those operations. See [SDK integration](docs/sdk-integration.md).

REC decoding is separate and experimental. It requires a separately installed,
supported SDK revision plus a user-built local decoder:

```bash
polar-ble sdk decoder build
polar-ble rec status
polar-ble rec decode PPI0.REC --output PPI0.jsonl
```

The project distributes neither the SDK nor a decoder binary. The initial
end-to-end validation covers unencrypted `PPI` recordings from Polar Loop Gen
2; other recording categories are emitted through the same generic JSONL
envelope but remain unvalidated.

## Documentation and development

- [Configuration and CLI](docs/configuration.md)
- [Architecture](docs/architecture.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Contributor guide](CONTRIBUTING.md)
- [Development](docs/development.md)
- [Release process](docs/releasing.md)

## Licence and trademarks

Project-authored content is licensed under the
[Apache License 2.0](LICENSE). See [NOTICE](NOTICE) for attribution, trademark,
and SDK-separation notices.

Polar and related product names are trademarks of Polar Electro Oy and are used
solely to identify compatible devices.
