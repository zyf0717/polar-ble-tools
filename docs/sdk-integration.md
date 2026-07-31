# SDK integration

Discovery, BLE preparation, PMD/PFTP operations, raw `.REC` retrieval, passive
`.BPB` retrieval, hashing, storage, and cleanup do not require the Polar BLE
SDK.
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
polar-ble sdk schemas verify
```

`sdk install` stages the pinned source, inspects descriptors, resolves the
required dependency closure, generates Python modules, verifies hashes,
imports, symbols, and descriptors, then activates the SDK source and generated
schema revision.
Generation or verification failure leaves the previously active verified
revisions unchanged.

SDK source and generated schemas have independent status and activation:

```bash
polar-ble sdk status
polar-ble sdk schemas status
polar-ble sdk schemas verify
polar-ble sdk schemas activate --commit FULL_REVISION
```

New format-3 caches bind source, descriptor, generated-file, and toolchain
provenance in their local manifest. They can be verified and used without
retaining the SDK checkout. Existing format-2 caches remain usable only while
their matching verified source is installed; regenerate them before
source-only removal.

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
download or generate SDK material. Removal accepts one or more exact full
commit SHAs, or every SDK/schema entry:

```bash
polar-ble sdk remove --commit FULL_REVISION
polar-ble sdk remove --commit FULL_REVISION --commit ANOTHER_FULL_REVISION
polar-ble sdk remove --all
polar-ble sdk remove --commit FULL_REVISION --retain-schemas
```

Add `--dry-run` to inspect deterministic per-commit outcomes without mutation.
Bulk removal prompts for confirmation; use `--yes` for unattended execution.
SDK removal retains matching decoder runtimes and workspaces unless
`--include-decoders` is supplied:

```bash
polar-ble sdk remove --commit FULL_REVISION --include-decoders --dry-run
polar-ble sdk remove --all --include-decoders --yes
```

`--retain-schemas` removes SDK source only and requires any matching generated
cache to be verified format 3. It preserves the independent schema pointer.
Removing selected schemas, SDK source, or a decoder clears only the
corresponding activation pointer.
Already-absent exact targets are successful idempotent outcomes. Every target
is preflighted before deletion begins, and paths must remain exact regular
directories under their configured roots. The shared JDK is never removed by
`sdk remove`; a selected decoder workspace, including its per-commit Gradle
files and dependency cache, is removed when decoder inclusion is requested.

This project does not grant rights to the Polar BLE SDK. The user's SDK copy,
schema source, generated modules, and descriptor sets remain governed by the
terms under which the user obtained them.

The licensed local BPB contract suite accepts
`POLAR_BLE_BPB_FIXTURE_MANIFEST=/absolute/path/to/manifest.json`. The external
JSON object contains a non-empty `fixtures` list. Each row supplies `path`,
`device_path`, and `expected_schema_id`, with optional `expected_raw_sha256`,
`expected_json_sha256`, and dotted `expected_fields`. Fixture files, manifests,
decoded values, and generated bindings must remain outside Git and public CI.

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
