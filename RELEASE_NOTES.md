# polar-ble-tools 0.4.0

`0.4.0` adds official-schema BPB decoding and hardens the optional local SDK
and REC-decoder lifecycles.

## BPB decoding

- Decode supported local BPB files with Python bindings generated from a
  separately obtained official Polar BLE SDK checkout.
- Decode collection and passive manifests, or opt in during retrieval with
  `polar-ble passive collect --decode`.
- Preserve raw evidence while publishing owner-private decoded JSON atomically.
- Record schema commit, manifest format, descriptor digest, message type,
  logical-date source, decoded path, and decoded digest in additive passive
  manifest version-2 rows.
- Reject unknown paths, unsafe inputs and outputs, incomplete messages, digest
  mismatches, and payload/path date disagreement with stable result codes.

## SDK and schema lifecycle

- Generated format-3 schema caches remain independently verifiable and usable
  after the matching SDK source checkout is removed.
- `polar-ble sdk remove --retain-schemas` removes exact SDK source revisions
  while preserving verified format-3 schemas.
- SDK removal supports multiple exact revisions or all revisions, deterministic
  dry runs, explicit decoder inclusion, and guarded bulk confirmation.
- Every SDK install or download requires fresh explicit licence confirmation;
  unattended callers use `--yes`.

## REC decoder lifecycle

- Added immutable Linux x86_64 and aarch64 toolchain descriptors, architecture
  normalization, descriptor-bound offline cache reuse, and platform mismatch
  diagnostics.
- Decoder runtimes bind the exact SDK commit and SDK licence digest used to
  build them. Local decoder attribution is not an SDK licence acceptance
  record.
- Decomposed the Python and JVM decoder implementations without changing the
  public single-file REC decoding API.

## Compatibility evidence

- Polar Loop Gen 2 `device_version` 6.1.19: controlled retrieval and decoding
  covered seven logical days each of activity samples, daily summaries, and
  skin-temperature periods—21 real BPB files with no unsupported or failed
  decodes.
- Polar Verity Sense `device_version` 3.0.16: controlled PMD status and bounded
  raw REC retrieval remain covered for ACC, GYRO, HR, MAGNETOMETER, PPG, and
  PPI. Passive BPB domains remain unclaimed because the device exposed no files.
- Sleep, nightly-recharge, and automatic-sample BPB device compatibility is not
  claimed because no real files were present in the bounded Loop Gen 2 window.
- Structured REC decoding remains experimental, local-only, and limited to the
  evidence in the compatibility matrix. Batch, protected, and encrypted REC
  decoding are not included.

## Fixes

- Restored expected Gradle launcher permissions after safe ZIP extraction.
- Removed an SDK-tooling import cycle that could prevent `doctor` from loading
  REC and schema status together.
- `doctor` reports active SDK/decoder commit mismatches without disabling an
  otherwise verified decoder.

## Distribution boundary

The distributions contain no Polar SDK source, schema source, generated
bindings, descriptor sets, recordings, captures, device inventories, profiles,
credentials, decoder runtimes, or hardware logs. SDK-derived and device-derived
material remains private and outside the repository and package artifacts.

## Documentation

- [SDK integration](https://github.com/zyf0717/polar-ble-tools/blob/main/docs/sdk-integration.md)
- [CLI reference](https://github.com/zyf0717/polar-ble-tools/blob/main/docs/cli-reference.md)
- [Python API](https://github.com/zyf0717/polar-ble-tools/blob/main/docs/python-api.md)
- [Compatibility](https://github.com/zyf0717/polar-ble-tools/blob/main/docs/compatibility.md)
- [Release process](https://github.com/zyf0717/polar-ble-tools/blob/main/docs/releasing.md)
