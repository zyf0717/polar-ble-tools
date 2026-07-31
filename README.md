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

## Capabilities

- manage supported PMD offline recordings and recording settings;
- list, retrieve, and manage device-resident files through PFTP;
- retrieve raw `.REC` recordings with SHA-256 manifests and guarded cleanup;
- retrieve passive `.BPB` files and decode supported data with local schemas;
- discover devices, prepare fresh Linux devices, and run bounded managed
  sessions through Bleak;
- validate and apply first-time-use (FTU) data;
- generate and verify optional local schemas from a separately obtained SDK;
- locally decode supported `.REC` files to validated JSONL with an optional SDK sidecar.

## Installation

Device operations require Linux and BlueZ. Python 3.11 or newer is required;
versions 3.11 through 3.14 are tested. The package uses Bleak for scanning and
device sessions. Fresh Linux
preparation lazily uses a narrow D-Bus BlueZ authentication agent; no
`bluetoothctl` subprocess is required.

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

Discover, prepare, and probe a device:

```bash
polar-ble discover --timeout 15 --name Polar
polar-ble prepare --device-identifier AA:BB:CC:DD:EE:FF
polar-ble connect --device-identifier AA:BB:CC:DD:EE:FF
```

`prepare` first checks pair-free readiness, uses the target-bound Linux agent
only when authentication is required, then verifies an agent-free reconnect.
`connect` is a readiness probe; both commands finish disconnected.

### First-time setup for Polar Loop Gen 2

For a Loop Gen 2 that has not completed first-time setup, copy the
[Loop Gen 2 FTU profile example](https://github.com/zyf0717/polar-ble-tools/blob/main/docs/loop-gen2-ftu-profile.example.json)
to a private location and replace every value. The profile contains personal
physical data and must not be committed or placed in shared logs. FTU requires
the optional generated-schema cache installed above.

Validate the profile without contacting the device, then apply it and confirm
completion:

```bash
polar-ble ftu dry-run \
  --profile ~/.config/polar-ble-tools/ftu-profile.json
polar-ble ftu --device-identifier AA:BB:CC:DD:EE:FF apply \
  --profile ~/.config/polar-ble-tools/ftu-profile.json
polar-ble ftu --device-identifier AA:BB:CC:DD:EE:FF status
```

### First-time setup for Polar Verity Sense

Copy the
[Verity Sense FTU profile example](https://github.com/zyf0717/polar-ble-tools/blob/main/docs/verity-sense-ftu-profile.example.json)
to a private location and select the wear location. Validate and apply it with
the same `ftu dry-run` and `ftu apply` commands. Verity FTU sets system/local
time from the timezone-aware host clock after connecting, then applies wear
location. Time is runtime state and is not stored in the profile. Pool length
is rejected because its device write contract is not supported.

### Passive data from Polar Loop Gen 2

After the device has accumulated data, replace the example dates with the
bounded range to retrieve. Collection persists and hashes the raw `.BPB` files
before optional decoding:

```bash
polar-ble passive --device-identifier AA:BB:CC:DD:EE:FF \
  --from-date 2026-07-23 --to-date 2026-07-29 collect --decode
```

Omit `--decode` to collect raw passive files without an active schema cache.

### Offline REC recordings

Polar Loop Gen 2 and Polar Verity Sense both support the raw REC workflow.
Inspect the device-supported types and settings, start an ACC recording, then
stop and collect it after the desired duration:

```bash
polar-ble raw --device-identifier AA:BB:CC:DD:EE:FF types
polar-ble raw --device-identifier AA:BB:CC:DD:EE:FF \
  settings --type ACC --full
polar-ble raw --device-identifier AA:BB:CC:DD:EE:FF \
  start --type ACC --setting sample_rate=52
# Run the stop command after the desired recording duration.
polar-ble raw --device-identifier AA:BB:CC:DD:EE:FF stop --type ACC
polar-ble raw --device-identifier AA:BB:CC:DD:EE:FF collect --type ACC
```

Raw REC collection is SDK-free. Structured REC decoding is a separate,
experimental workflow requiring the optional local sidecar.

See [device setup](https://github.com/zyf0717/polar-ble-tools/blob/main/docs/device-setup.md)
for the complete FTU workflow. See
[offline recording](https://github.com/zyf0717/polar-ble-tools/blob/main/docs/offline-recording.md),
[raw retrieval](https://github.com/zyf0717/polar-ble-tools/blob/main/docs/raw-file-retrieval.md),
and [REC decoding](https://github.com/zyf0717/polar-ble-tools/blob/main/docs/rec-decoding.md)
for the complete REC workflows and supported types.

## Compatibility

Controlled hardware validation covers Polar Loop Gen 2 and Polar Verity Sense
on Linux/BlueZ. Other devices exposing the required PMD and PFTP services may
work but are not confirmed for this release. See
[compatibility](https://github.com/zyf0717/polar-ble-tools/blob/main/docs/compatibility.md)
for the verified capability matrix and limitations.

## Optional SDK functionality

The package does not distribute the Polar BLE SDK, Polar SDK schema files, or
artefacts generated from those files. Optional SDK-assisted functionality uses
an SDK copy separately obtained and licensed by the user. SDK operations are
explicit commands; package installation and import never download, generate,
or activate SDK material. Structured REC decoding additionally requires a
locally built optional sidecar. See
[SDK integration](https://github.com/zyf0717/polar-ble-tools/blob/main/docs/sdk-integration.md),
[REC decoding](https://github.com/zyf0717/polar-ble-tools/blob/main/docs/rec-decoding.md),
and [compatibility](https://github.com/zyf0717/polar-ble-tools/blob/main/docs/compatibility.md)
for prerequisites and evidence-backed limitations.

## Documentation

- [Device setup](https://github.com/zyf0717/polar-ble-tools/blob/main/docs/device-setup.md)
- [Configuration and CLI](https://github.com/zyf0717/polar-ble-tools/blob/main/docs/configuration.md)
- [CLI reference](https://github.com/zyf0717/polar-ble-tools/blob/main/docs/cli-reference.md)
- [Python API reference](https://github.com/zyf0717/polar-ble-tools/blob/main/docs/python-api.md)
- [Compatibility](https://github.com/zyf0717/polar-ble-tools/blob/main/docs/compatibility.md)
- [Troubleshooting](https://github.com/zyf0717/polar-ble-tools/blob/main/docs/troubleshooting.md)
- [Contributor guide](https://github.com/zyf0717/polar-ble-tools/blob/main/CONTRIBUTING.md)

## Licence and trademarks

Project-authored content is licensed under the
[Apache License 2.0](https://github.com/zyf0717/polar-ble-tools/blob/main/LICENSE).
See [NOTICE](https://github.com/zyf0717/polar-ble-tools/blob/main/NOTICE) for
attribution, trademark, and SDK-separation notices.

Polar and related product names are trademarks of Polar Electro Oy and are used
solely to identify compatible devices.
