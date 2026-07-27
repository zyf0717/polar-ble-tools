# polar-ble-tools

[![PyPI](https://img.shields.io/pypi/v/polar-ble-tools?label=pypi)](https://pypi.org/project/polar-ble-tools/)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-Apache--2.0-yellow.svg)](https://github.com/zyf0717/polar-ble-tools/blob/main/LICENSE)

Offline-first Python tools for on-device data collection and local retrieval from supported Polar wearable devices over Bluetooth Low Energy.

Currently supported devices are **Polar Loop Gen 2** and **Polar Verity Sense**.
Support is limited to the controlled, device-specific behavior documented in
the compatibility matrix.

`polar-ble-tools` supports workflows in which a wearable records data to its
own storage and the resulting files are retrieved later over BLE. It provides
device setup, offline recording control, PFTP file retrieval, integrity
manifests, guarded cleanup, and optional local decoding for supported formats.
Data collection and retrieval do not require Polar Flow.

This repository is deliberately limited to BLE tooling: protocol access,
device-facing operations, local persistence safeguards, and helpers
that make one BLE operation safe and usable. Higher-level application
orchestration belongs in an orchestration layer built on these APIs, and is
out of scope for this project.

> `polar-ble-tools` is an unofficial community project. It is not affiliated
> with, endorsed by, sponsored by, or maintained by Polar Electro Oy.

## Data collection workflow

The package supports a device-resident collection lifecycle:

1. discover, pair, and prepare a supported wearable through Linux BlueZ;
2. inspect supported PMD recording capabilities and configure an offline recording;
3. allow the wearable to collect data into its own storage;
4. reconnect over BLE and enumerate files through PFTP;
5. retrieve `.REC` or `.BPB` files into local storage;
6. verify retrieved files using recorded size and SHA-256 metadata;
7. review guarded cleanup decisions before removing verified device files;
8. decode supported formats locally when the required optional tooling is available.

## Capabilities

- manage supported PMD offline recordings and recording settings;
- list, retrieve, and manage device-resident files through PFTP;
- retrieve raw `.REC` recordings with SHA-256 manifests and guarded cleanup;
- retrieve passive `.BPB` files and decode supported data with local schemas;
- discover, pair, trust, and connect devices through Linux BlueZ;
- validate and apply first-time-use (FTU) data;
- generate and verify optional local schemas from a separately obtained SDK;
- locally decode supported `.REC` files to validated JSONL with an optional SDK sidecar.

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
polar-ble sdk install
```

The installer asks for a simple `y/N` confirmation that proceeding accepts the
Polar BLE SDK licence. This happens on every install/download invocation,
including cache reuse. Use `-y` for non-interactive installation.

## Quick start

Discover and pair a device:

```bash
polar-ble discover --scan-seconds 15 --name Polar
polar-ble pair --mac-address AA:BB:CC:DD:EE:FF --scan-seconds 15
```

List device-resident files:

```bash
polar-ble raw --mac-address AA:BB:CC:DD:EE:FF list
```

Collect raw recordings:

```bash
polar-ble raw --mac-address AA:BB:CC:DD:EE:FF collect
```

Review a cleanup without deleting device files:

```bash
polar-ble raw --mac-address AA:BB:CC:DD:EE:FF cleanup --all --dry-run
```

See [device setup](https://github.com/zyf0717/polar-ble-tools/blob/main/docs/device-setup.md),
[offline recording](https://github.com/zyf0717/polar-ble-tools/blob/main/docs/offline-recording.md),
and [raw retrieval](https://github.com/zyf0717/polar-ble-tools/blob/main/docs/raw-file-retrieval.md)
before performing device mutations.

## Compatibility

Controlled hardware validation covers Polar Loop Gen 2 and Polar Verity Sense
on Linux/BlueZ. Other devices exposing the required PMD and PFTP services may
work but are not confirmed for this release. See
[compatibility](https://github.com/zyf0717/polar-ble-tools/blob/main/docs/compatibility.md)
for the verified capability matrix and limitations.

## Optional SDK-assisted functionality

The package does not distribute the Polar BLE SDK, Polar SDK schema files, or
artefacts generated from those files. Optional SDK-assisted functionality uses
an SDK copy separately obtained and licensed by the user.

SDK download, inspection, generation, verification, activation, and removal are
explicit `polar-ble sdk` commands. Package installation and import never perform
those operations. See
[SDK integration](https://github.com/zyf0717/polar-ble-tools/blob/main/docs/sdk-integration.md).

REC decoding is optional and local-only. It requires a separately installed SDK
and a user-built decoder; no SDK source or decoder binary is distributed:

```bash
polar-ble sdk decoder build
polar-ble rec status
polar-ble rec decode PPI0.REC --output PPI0.jsonl
```

See [REC decoding](https://github.com/zyf0717/polar-ble-tools/blob/main/docs/rec-decoding.md)
for prerequisites, protocol, cache, security boundary, and limitations; see
[compatibility](https://github.com/zyf0717/polar-ble-tools/blob/main/docs/compatibility.md)
for the evidence-backed matrix.

## Documentation and development

- [Configuration and CLI](https://github.com/zyf0717/polar-ble-tools/blob/main/docs/configuration.md)
- [CLI reference](https://github.com/zyf0717/polar-ble-tools/blob/main/docs/cli-reference.md)
- [Python API reference](https://github.com/zyf0717/polar-ble-tools/blob/main/docs/python-api.md)
- [Architecture](https://github.com/zyf0717/polar-ble-tools/blob/main/docs/architecture.md)
- [Troubleshooting](https://github.com/zyf0717/polar-ble-tools/blob/main/docs/troubleshooting.md)
- [Contributor guide](https://github.com/zyf0717/polar-ble-tools/blob/main/CONTRIBUTING.md)
- [Development](https://github.com/zyf0717/polar-ble-tools/blob/main/docs/development.md)
- [Release process](https://github.com/zyf0717/polar-ble-tools/blob/main/docs/releasing.md)
- [0.3.2 release notes](https://github.com/zyf0717/polar-ble-tools/blob/main/RELEASE_NOTES.md)

## Licence and trademarks

Project-authored content is licensed under the
[Apache License 2.0](https://github.com/zyf0717/polar-ble-tools/blob/main/LICENSE).
See [NOTICE](https://github.com/zyf0717/polar-ble-tools/blob/main/NOTICE) for
attribution, trademark, and SDK-separation notices.

Polar and related product names are trademarks of Polar Electro Oy and are used
solely to identify compatible devices.
