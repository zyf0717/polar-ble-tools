# SPEC-REC-001: Optional SDK-backed `.REC` decoder sidecar

**Status:** Proposed
**Target:** `polar-ble-tools` 0.2.0
**Repository baseline:** `main` at `6d087f8249cfb658f9752c96b1da74e566e8b02a`
**Implementation branch:** `feat/rec-decoder-sidecar`

## 1. Decision summary

Add structured `.REC` decoding as an **optional local sidecar** built by the user from a separately obtained Polar BLE SDK checkout.

`polar-ble-tools` will:

- continue to retrieve and preserve raw `.REC` files without schemas or SDK tooling;
- expose a stable project-owned Python API and CLI for decoding;
- build, verify, activate, invoke, and remove a decoder executable in the user data directory;
- communicate with the executable through a versioned, streaming JSONL protocol;
- never distribute the Polar SDK, SDK-derived source, generated SDK artifacts, or compiled decoder binaries.

The sidecar will:

- be built only after an explicit user command;
- call the official decoder implementation from the user's local SDK checkout;
- return project-owned normalized output rather than Kotlin, Swift, or SDK object types;
- run out of process so vendor dependencies cannot leak into the Python runtime.

## 2. Goals

1. Decode local `.REC` files without manually porting the official Kotlin or Swift decoder.
2. Preserve the existing licensing and packaging boundary.
3. Keep raw retrieval independent from decoding availability.
4. Provide deterministic, machine-readable output suitable for downstream storage and analysis.
5. Fail clearly when the SDK, build toolchain, compatible decoder, or verified sidecar is unavailable.
6. Make almost all Python behavior testable without downloading the Polar SDK or requiring hardware.

## 3. Non-goals

- Shipping a decoder binary in wheels, sdists, GitHub releases, or CI artifacts.
- Shipping or copying Polar SDK source, generated schemas, or SDK-derived files.
- Translating the official decoder into Python.
- Automatically building a decoder during package installation, import, SDK installation, or schema generation.
- Decoding files directly during BLE collection.
- Supporting CSV, Parquet, databases, or analytics transformations in the first release.
- Guaranteeing support for every Polar device or `.REC` variant.
- Running unverified decoder executables by default.
- Adding cloud decoding or remote execution.

## 4. Architectural invariants

These requirements are mandatory:

1. `polar_ble_tools.rec` must import successfully on a clean installation with no SDK, JDK, Gradle, Android SDK, or decoder.
2. `polar-ble raw` behavior must remain unchanged and must never invoke the decoder.
3. `polar-ble sdk install --accept-license` must not build the decoder.
4. Package installation and module import must perform no download, generation, build, or activation.
5. Decoder build output must remain under the user-owned cache/data root.
6. The Python package must not import or expose SDK classes.
7. Runtime invocation must use argument arrays, never `shell=True`.
8. Destination files must be written atomically and must not be overwritten unless explicitly requested.
9. A decoder is usable only when its manifest, executable digest, protocol version, and verification state are valid.
10. Public CI must not download the Polar SDK or publish locally built decoder artifacts.

## 5. High-level architecture

```text
polar-ble-tools
├── raw retrieval and storage                 existing; unchanged
├── polar_ble_tools.rec                       stable public facade
│   ├── status and capability detection
│   ├── decode orchestration
│   ├── project-owned result models
│   └── protocol validation
├── polar_ble_tools.sdk_tools.decoder         local lifecycle tooling
│   ├── feasibility/discovery
│   ├── build workspace generation
│   ├── build and activation
│   ├── manifest verification
│   └── removal
└── local decoder executable                  never distributed
    └── official SDK decoder implementation
```

Recommended package layout:

```text
src/polar_ble_tools/
├── rec/
│   ├── __init__.py
│   ├── api.py
│   ├── errors.py
│   ├── models.py
│   ├── protocol.py
│   └── runtime.py
├── commands/
│   └── rec.py
└── sdk_tools/
    ├── decoder/
    │   ├── __init__.py
    │   ├── builder.py
    │   ├── discovery.py
    │   ├── manifest.py
    │   ├── verifier.py
    │   └── workspace.py
    └── decoder_project/
        ├── project-owned build templates
        └── project-owned Kotlin adapter source
```

The adapter source may be distributed because it is project-authored. It must not contain copied SDK implementation code.

## 6. Feasibility gate

Do not begin the production adapter until a focused feasibility spike confirms the official SDK integration path.

Create:

```text
docs/decisions/rec-sidecar-feasibility.md
```

The spike must identify:

- the exact supported Polar SDK commit;
- the official `.REC` decode entry point and required modules;
- whether the decoder can run on a plain JVM;
- whether Android SDK/runtime classes are required;
- the minimum JDK, Gradle, Kotlin, and optional Android toolchain versions;
- whether the decoder can be invoked without modifying vendor source;
- the decoded record categories available from at least one locally owned sample;
- any SDK API instability or internal/private API use;
- build and runtime licence implications requiring user action;
- the recommended build mode.

Permitted build modes, in priority order:

1. **Pure JVM adapter:** preferred when the required SDK modules compile without Android runtime dependencies.
2. **Headless Android/JVM adapter:** allowed when the official decoder requires Android build tooling but can execute locally without a device or emulator.

Stop and report instead of implementing the feature if the official implementation requires:

- copying substantial vendor source into this repository;
- manually translating the decoder;
- patching the SDK in a way that cannot be generated reproducibly outside the repository;
- redistributing restricted binaries;
- unsupported runtime behavior that cannot be verified.

## 7. Local lifecycle and cache

Extend `SdkCache` without changing existing SDK/schema paths.

```text
<user-data-root>/
├── sdk/polar/<sdk-commit>/                 existing
├── generated/polar/<sdk-commit>/           existing
├── decoder-build/polar/<sdk-commit>/       generated build workspace
├── decoder/polar/<sdk-commit>/
│   ├── bin/ or decoder.jar
│   ├── manifest.json
│   ├── build-report.json
│   └── verify-report.json
├── active-sdk.json                         existing
└── active-decoder.json                     new
```

Required `SdkCache` additions:

```python
decoder_build_root
decoder_root
active_decoder_manifest_path
decoder_build_path(commit)
decoder_path(commit)
```

### 7.1 Independence from schema generation

The schema and decoder lifecycles are related by SDK provenance but remain independent:

- schema generation may succeed while decoder build is unavailable;
- decoder build may succeed without regenerating schemas;
- activating an SDK revision must not activate a decoder;
- activating a decoder must not change the active schema revision;
- deleting generated schemas must not delete a decoder;
- decoder removal must be explicit.

### 7.2 Decoder manifest

`manifest.json` must contain at least:

```json
{
  "manifest_version": 1,
  "decoder_protocol_version": 1,
  "sdk_commit": "<full commit>",
  "polar_ble_tools_version": "<version>",
  "build_mode": "jvm|android-jvm",
  "build_timestamp_utc": "<RFC3339>",
  "platform": "<normalized platform>",
  "architecture": "<normalized architecture>",
  "java_version": "<version>",
  "gradle_version": "<version>",
  "adapter_source_sha256": "<digest>",
  "executable_relative_path": "<path>",
  "executable_sha256": "<digest>",
  "verification_level": "handshake|sample",
  "verified": true
}
```

Never store licence text, SDK source, personal paths, device identifiers, or recording data in the manifest.

### 7.3 Activation

Build into a staging directory. Activate only after verification succeeds.

Activation must be atomic:

1. complete build;
2. compute digests;
3. run structural verification;
4. write final manifest;
5. move staged output to the revision directory;
6. atomically replace `active-decoder.json`.

A failed build or verification must leave the previous active decoder unchanged.

## 8. Sidecar command contract

The built executable must support:

```text
polar-rec-decoder version
polar-rec-decoder self-test
polar-rec-decoder decode --input PATH --output PATH --protocol 1
```

Rules:

- stdout contains exactly one final machine-readable JSON status object;
- diagnostics and logs go to stderr;
- decoded content goes only to the requested output path;
- successful commands exit `0`;
- invalid usage exits `2`;
- unsupported input exits `3`;
- internal decode failure exits `4`;
- protocol incompatibility exits `5`;
- output must not be partially presented as successful.

The Python runtime may support either a native launcher or `java -jar`, but the manifest must define the exact argument array.

## 9. Decoder protocol v1

The first output format is UTF-8 JSON Lines.

### 9.1 Header

The first non-empty line must be:

```json
{
  "type": "header",
  "protocol_version": 1,
  "sdk_commit": "<full commit>",
  "decoder_version": "<adapter version>",
  "source_sha256": "<digest>"
}
```

### 9.2 Records

Each decoded record must use a project-owned envelope:

```json
{
  "type": "record",
  "record_type": "<normalized-slug>",
  "timestamp_ns": 1234567890,
  "payload": {}
}
```

Requirements:

- `record_type` is a stable lowercase project-owned slug;
- `timestamp_ns` is an integer UTC Unix timestamp in nanoseconds or `null`;
- `payload` contains only JSON-compatible project-owned keys and values;
- SDK/Kotlin/Swift class names must not be required by callers;
- unknown but valid fields may be preserved inside `payload`;
- non-finite numbers must be encoded as `null` and reported as warnings;
- binary values must be base64 with an explicit encoding field;
- records must preserve source order unless the official decoder defines a stronger ordering;
- output from the same input, decoder build, and protocol version should be deterministic.

Do not promise semantic normalization that the feasibility spike cannot validate. Prefer a generic stable envelope over speculative domain models.

### 9.3 Summary

The final line must be:

```json
{
  "type": "summary",
  "record_count": 0,
  "record_types": {},
  "warnings": []
}
```

The Python runtime must reject:

- missing or duplicate headers;
- an incompatible protocol version;
- malformed JSON;
- records after the summary;
- a missing summary;
- a source digest mismatch;
- a sidecar success response that disagrees with the output summary.

## 10. Public Python API

Expose from `polar_ble_tools.rec`:

```python
def decoder_status() -> DecoderStatus:
    ...

def decode_recording(
    source: PathLike[str] | str,
    destination: PathLike[str] | str,
    *,
    overwrite: bool = False,
    timeout_seconds: float | None = None,
) -> DecodeReport:
    ...

def iter_decoded_records(
    decoded_jsonl: PathLike[str] | str,
) -> Iterator[RecRecord]:
    ...
```

Required models:

```python
@dataclass(frozen=True)
class DecoderStatus:
    available: bool
    verified: bool
    sdk_commit: str | None
    protocol_version: int | None
    verification_level: str | None
    reason: str | None

@dataclass(frozen=True)
class DecodeReport:
    source_path: Path
    destination_path: Path
    source_sha256: str
    destination_sha256: str
    sdk_commit: str
    decoder_version: str
    record_count: int
    record_types: Mapping[str, int]
    warnings: tuple[str, ...]

@dataclass(frozen=True)
class RecRecord:
    record_type: str
    timestamp_ns: int | None
    payload: Mapping[str, object]
```

Do not return sidecar process objects, SDK objects, unvalidated dictionaries, or vendor-specific models.

### 10.1 Errors

Define:

```text
RecDecodeError
├── DecoderUnavailableError
├── DecoderManifestError
├── DecoderVerificationError
├── DecoderProtocolError
├── DecoderTimeoutError
└── RecordingDecodeError
```

Errors must include actionable remediation without exposing excessive subprocess output. Truncate captured stderr to a bounded size.

## 11. CLI

Add a top-level `rec` command, separate from `raw`.

```text
polar-ble rec decode INPUT --output OUTPUT
polar-ble rec decode INPUT --output OUTPUT --overwrite
polar-ble rec status
```

Add decoder lifecycle commands beneath `sdk`:

```text
polar-ble sdk decoder build [--commit COMMIT] [--no-activate]
polar-ble sdk decoder verify [--commit COMMIT] [--sample PATH]
polar-ble sdk decoder status [--json]
polar-ble sdk decoder activate --commit COMMIT
polar-ble sdk decoder remove --commit COMMIT
```

Behavior:

- `build` uses the active SDK revision unless `--commit` is supplied;
- `build` never downloads the SDK;
- licence acceptance must already be recorded by the existing explicit SDK installation flow;
- `verify` without `--sample` performs manifest, digest, version, and self-test checks;
- `verify --sample` performs an end-to-end local decode and records `verification_level=sample`;
- `status` succeeds even when unavailable and explains why;
- `decode` requires an active verified decoder;
- `remove` must not affect raw files, schemas, or SDK sources;
- removing the active decoder clears `active-decoder.json` atomically.

Extend `polar-ble doctor` with an optional decoder section. Decoder unavailability must not make core BLE/raw readiness fail.

## 12. Build behavior

The builder must:

1. resolve a locally installed SDK revision;
2. validate its recorded provenance and full commit;
3. generate a clean build workspace outside the repository;
4. copy only project-owned adapter/build templates into that workspace;
5. reference the SDK through its local cached path;
6. run the selected toolchain without `shell=True`;
7. capture a bounded build log and structured build report;
8. locate exactly one expected executable artifact;
9. reject unexpected SDK-derived files in the final decoder directory;
10. verify and activate atomically.

Network behavior:

- never download the Polar SDK;
- ordinary Maven/Gradle dependency resolution may occur during an explicit build;
- provide an `--offline` build option if the selected toolchain supports it;
- document all external prerequisites and any network access.

The builder must not edit the cached SDK checkout in place.

## 13. Runtime safety

The Python runtime must:

- resolve the active decoder only from `active-decoder.json`;
- ensure all resolved paths remain under the decoder cache root;
- verify the executable digest before invocation;
- use a temporary destination in the final destination directory;
- reject symlink/path traversal surprises where practical;
- reject missing, non-regular, or unreadable input;
- reject an existing destination unless `overwrite=True`;
- enforce a configurable timeout;
- terminate the child process on timeout;
- bound captured stdout and stderr;
- validate the complete JSONL stream before atomic rename;
- remove temporary output after failure;
- never delete or modify the source `.REC`;
- never invoke device or BLE operations.

## 14. Testing strategy

### 14.1 Mandatory public CI tests

Use a project-owned fake sidecar executable. No Polar SDK or real decoder is required.

Add tests for:

- clean import with no decoder;
- unavailable status and remediation;
- valid manifest discovery;
- digest mismatch rejection;
- protocol version mismatch;
- malformed stdout status;
- malformed JSONL;
- missing header or summary;
- source digest mismatch;
- non-zero child exit;
- timeout and child termination;
- bounded stderr handling;
- atomic output;
- overwrite protection;
- temporary-file cleanup;
- record iteration;
- CLI exit behavior;
- active-decoder activation and rollback;
- decoder removal;
- `doctor` reporting;
- existing `raw` tests remaining unchanged.

### 14.2 Builder tests without vendor content

Create a tiny project-owned fake SDK/build fixture only if useful for build orchestration tests. It must not copy or approximate vendor decoder implementation.

Test:

- workspace generation;
- toolchain command construction;
- staging and activation;
- failed build rollback;
- final-artifact allowlisting;
- manifest generation;
- offline flag propagation.

### 14.3 Local SDK contract tests

Mark real SDK tests separately, for example:

```text
tests/sdk_decoder_contract/
```

They must be skipped unless explicitly enabled with local environment variables and prerequisites.

At minimum validate:

- adapter compiles against the pinned SDK commit;
- `version` and `self-test` succeed;
- one user-supplied sanitized `.REC` sample decodes;
- output passes Python protocol validation;
- output is deterministic across two runs;
- no SDK source or recording data appears in the final decoder directory.

Never commit personal or identifiable recordings. Commit a `.REC` fixture only after confirming provenance, sanitization, and redistribution suitability.

### 14.4 Packaging tests

Expand packaging artifact checks to fail if a wheel, sdist, release artifact, or repository-tracked output contains:

```text
*.jar
*.class
*.aar
decoder/polar/
decoder-build/polar/
cached SDK source
generated SDK schema output
local .REC samples
```

Project-authored `.kt`, `.kts`, or build templates are allowed only from the designated adapter template directory.

## 15. Documentation

Update:

- `README.md`
  - replace “Structured `.REC` decoding is not currently included” with optional sidecar status;
  - retain the raw-retrieval-first guidance.
- `docs/architecture.md`
  - add the sidecar boundary and data flow.
- `docs/sdk-integration.md`
  - explain that schema and decoder lifecycles are separate.
- `docs/configuration.md`
  - document commands, paths, timeout, and status.
- `docs/troubleshooting.md`
  - cover missing SDK, JDK/Gradle/Android prerequisites, build failure, incompatible protocol, verification failure, and unsupported recording.
- `NOTICE`
  - clarify that decoder binaries are locally built and not distributed.
- `docs/compatibility.md`
  - add a device/recording decoder validation matrix.
- `docs/releasing.md`
  - add artifact scans and a prohibition on decoder release uploads.

Documentation must state that:

- the project is unofficial;
- the user separately obtains and accepts the SDK licence;
- decoding support depends on the locally built decoder and validated SDK revision;
- raw collection remains available without the sidecar.

## 16. Implementation sequence

### Phase 0 — feasibility and decision record

1. Locate the official decode path in the pinned SDK.
2. Build the smallest external adapter manually in a temporary local workspace.
3. Decode one locally owned sample.
4. determine JVM versus Android/JVM requirements.
5. write `docs/decisions/rec-sidecar-feasibility.md`.
6. stop if any feasibility-gate condition fails.

**Gate:** no production adapter code before the decision record identifies a reproducible supported build path.

### Phase 1 — project-owned protocol and runtime

1. Create `polar_ble_tools.rec`.
2. Implement models, errors, manifest loading, status, subprocess runtime, JSONL validation, and atomic output.
3. Add a fake sidecar fixture.
4. Add comprehensive unit and CLI tests.
5. Add `polar-ble rec status|decode`.

**Gate:** all behavior works against the fake sidecar on public CI, with no SDK installation.

### Phase 2 — decoder cache and lifecycle

1. Extend `SdkCache`.
2. Add decoder manifest and active-manifest handling.
3. Add staged activation and rollback.
4. Add `sdk decoder status|verify|activate|remove`.
5. Extend `doctor`.
6. Add cache/lifecycle tests.

**Gate:** corrupt or failed decoder states cannot replace a previously valid active decoder.

### Phase 3 — reproducible local build

1. Add project-owned adapter and build templates.
2. Implement SDK/toolchain discovery.
3. Generate an isolated build workspace.
4. Build using the mode selected in Phase 0.
5. implement final-artifact allowlisting.
6. Add `sdk decoder build`.
7. Run structural verification before activation.
8. Add optional local SDK contract tests.

**Gate:** a clean local machine with documented prerequisites can build from the pinned SDK checkout and decode the validated sample.

### Phase 4 — hardening and documentation

1. Add malformed protocol, timeout, digest, path, rollback, and packaging tests.
2. Update all documentation and notices.
3. Confirm existing raw, BPB, schema, and SDK commands are unchanged.
4. Build wheel and sdist and inspect contents.
5. Run a full local end-to-end test.

**Gate:** definition of done is satisfied.

## 17. Definition of done

The feature is complete only when all of the following are true:

- [ ] `polar_ble_tools.rec` imports without optional tooling.
- [ ] Raw `.REC` retrieval remains fully usable without the decoder.
- [ ] `sdk install` does not build or activate a decoder.
- [ ] A decoder can be built explicitly from the supported local SDK revision.
- [ ] No vendor source or locally compiled decoder is tracked or distributed.
- [ ] Activation is atomic and rollback-safe.
- [ ] Runtime verifies provenance, protocol, and executable digest.
- [ ] Decode output uses validated protocol-v1 JSONL.
- [ ] Failed decoding leaves no successful-looking partial destination.
- [ ] The Python API and CLI return actionable errors.
- [ ] Public tests use only fake/project-owned fixtures.
- [ ] Local SDK contract tests pass against the pinned revision.
- [ ] Wheel and sdist artifact scans pass.
- [ ] Documentation clearly states prerequisites, support boundaries, and licensing separation.
- [ ] `ruff check .`, `pytest`, `python -m build`, and `twine check dist/*` pass.

## 18. Agent execution rules

1. Work only on `feat/rec-decoder-sidecar`.
2. Implement phases in order and keep each phase independently reviewable.
3. Prefer small commits with tests:
   - `docs: record REC decoder sidecar feasibility`
   - `feat(rec): add sidecar protocol and runtime`
   - `feat(sdk): add decoder cache lifecycle`
   - `feat(sdk): build local REC decoder sidecar`
   - `docs: document optional REC decoding`
4. Do not modify raw collection semantics or couple decode to retrieval.
5. Do not add new mandatory Python dependencies unless unavoidable and justified.
6. Do not commit SDK content, compiled outputs, build caches, or real recordings.
7. Do not weaken existing artifact-separation tests.
8. Do not silently fall back to unverified decoders.
9. Do not guess official SDK APIs; record exact findings in the feasibility decision.
10. When blocked by SDK/toolchain constraints, stop with a precise report rather than translating vendor code.
11. Before completion, inspect `git status`, the complete diff, wheel contents, and sdist contents.
12. Include in the PR description:
    - supported SDK commit;
    - build mode and prerequisites;
    - protocol version;
    - local validation performed;
    - explicit confirmation that no SDK or decoder binary is distributed.

## 19. Recommended release boundary

Release as `0.2.0`, not a `0.1.x` patch, because this adds:

- a new public Python namespace;
- new CLI commands;
- a versioned sidecar protocol;
- a new optional local toolchain lifecycle.

The decoder remains experimental until compatibility is validated across more than one recording type and device. Mark unsupported record types clearly rather than silently emitting incomplete data.
