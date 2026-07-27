# SDK integration

Discovery, pairing, PMD/PFTP operations, raw `.REC` retrieval, passive `.BPB`
retrieval, hashing, storage, and cleanup do not require the Polar BLE SDK.
Schema-backed FTU payload encoding and BPB decoding require a verified local
schema cache.

The project distribution does not include the Polar BLE SDK, Polar SDK schema
source files, or artefacts generated from those files.

## Explicit workflow

1. Install the optional compiler dependency.
2. Install the SDK, confirming that proceeding accepts Polar's licence.
3. Let the tool locate and inspect the required schema inputs.
4. Generate and verify the required runtime modules locally.
5. Keep the SDK source and generated artefacts outside the repository and
   distributions.

```bash
python -m pip install "polar-ble-tools[sdk]"
polar-ble doctor
polar-ble sdk install
polar-ble sdk verify
```

`sdk install` stages the pinned source, inspects descriptors, resolves the
required dependency closure, generates Python modules, verifies hashes,
imports, symbols, and descriptors, then atomically activates the revision.
Failure leaves the previously active verified revision unchanged.

The command asks `Continue? [y/N]`; continuing means the user accepts the Polar
BLE SDK licence. Use `polar-ble sdk install -y` for unattended installation.
The explicit Python `install_sdk()` API has the same proceed-means-accept
semantics and does not prompt.

Use `--sdk-path PATH` for a separately obtained local copy or `--ref REVISION`
for diagnostic evaluation. These overrides are content-addressed or revision
recorded but are not confirmed for this release.

Package installation, import, `doctor`, and ordinary device commands never
download or generate SDK material. Remove local cache data explicitly:

```bash
polar-ble sdk remove --commit FULL_REVISION
polar-ble sdk remove --all
```

This project does not grant rights to the Polar BLE SDK. The user's SDK copy,
schema source, generated modules, and descriptor sets remain governed by the
terms under which the user obtained them.

## Separate decoder lifecycle

Schema and REC decoder workflows are intentionally independent:

```text
schema:  sdk install -> inspect -> generate -> verify -> activate
decoder: sdk decoder build -> verify -> activate -> rec decode
```

`sdk install` does not build the decoder. The optional decoder uses the same
separately obtained SDK source but retains a separate local runtime, manifest,
and activation state. See [REC decoding](rec-decoding.md).
