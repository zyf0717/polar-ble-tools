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

Every install/download invocation asks `Continue? [y/N]`, including when the
requested SDK is already cached. Continuing means the user accepts the Polar
BLE SDK licence for that invocation. Use `polar-ble sdk install -y` for
unattended installation. Every explicit Python `install_sdk()` call has the
same proceed-means-accept semantics and does not prompt.

The package does not persist acceptance. A fresh explicit install/download
removes deprecated acceptance metadata and package-created standalone licence
copies from older SDK and generated-schema cache entries. The licence file
inside an SDK source tree remains part of that upstream source, not an
acceptance record.

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
and activation state. Only sidecars built and managed through this lifecycle are
supported. Externally managed sidecars are outside the package's verification
and compatibility scope.

During decoder build only, the exact SDK licence is copied from the pinned
checkout into the local decoder runtime as attribution material. The decoder
manifest binds its SHA-256 to the SDK commit and explicitly marks it as not an
acceptance record. Neither that file nor the compiled decoder is included in
PyPI distributions. Do not redistribute the locally compiled decoder under
this project's Apache-2.0 licence alone. See [REC decoding](rec-decoding.md).
