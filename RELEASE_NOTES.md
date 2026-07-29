# polar-ble-tools 0.4.1

`0.4.1` is a documentation-only patch that makes the supported device
workflows easier to find and follow from the package README.

## Quick start

- Separates Polar Loop Gen 2 first-time setup from its passive BPB collection
  workflow.
- Makes raw REC recording and collection a first-class workflow shared by
  Polar Loop Gen 2 and Polar Verity Sense.
- Provides a complete common ACC sequence: inspect types and settings, start
  and stop the recording, then collect the resulting REC file.
- Keeps raw REC and passive BPB collection SDK-free while identifying optional
  schema-backed BPB decoding and sidecar-backed structured REC decoding.
- Removes duplicated lifecycle guidance, incomplete raw commands, and advanced
  implementation material from the onboarding path.

## Compatibility and distribution

Runtime code, public APIs, device compatibility claims, and hardware evidence
are unchanged from `0.4.0`. The distributions continue to exclude Polar SDK
source, generated SDK artifacts, device data, profiles, credentials, and local
decoder runtimes.

## Documentation

- [Device setup](https://github.com/zyf0717/polar-ble-tools/blob/main/docs/device-setup.md)
- [Offline recording](https://github.com/zyf0717/polar-ble-tools/blob/main/docs/offline-recording.md)
- [Raw retrieval](https://github.com/zyf0717/polar-ble-tools/blob/main/docs/raw-file-retrieval.md)
- [Compatibility](https://github.com/zyf0717/polar-ble-tools/blob/main/docs/compatibility.md)
