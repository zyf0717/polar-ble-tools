# Functional requirements

## Offline-recording control surface

**FR-001** — Add high-level asynchronous Python APIs for:

```python
available_recording_types(...)
recording_status(...)
recording_settings(..., full=False)
start_recording(...)
stop_recording(...)
offline_trigger(...)
update_offline_trigger(...)
device_disk_space(...)
fetch_raw_recording(...)
```

**FR-002** — Export the APIs from a documented public module. Common operational APIs should be available from the top-level facade where consistent with the existing API policy.

**FR-003** — Add these CLI operations:

```text
polar-ble raw types
polar-ble raw status
polar-ble raw settings --type TYPE [--full]
polar-ble raw start --type TYPE [--setting KEY=VALUE ...]
polar-ble raw stop --type TYPE
polar-ble raw trigger get
polar-ble raw trigger set --mode MODE [--type TYPE ...] [--setting KEY=VALUE ...]
polar-ble raw disk-space
polar-ble raw fetch --path DEVICE_PATH --output LOCAL_PATH
```

**FR-004** — Reuse `OfflineRecordingControlClient`, `PmdClient`, `PftpClient`, `DeviceWorkflowRunner`, and existing project-owned models. Do not duplicate PMD packet construction in command modules.

**FR-005** — Validate measurement types and settings before opening a device
session where possible. Normalization, supported setting keys, integer bounds,
duplicate handling, and trigger-mode constraints are defined in
[Raw and passive operation contracts](operation-contracts.md).

**FR-006** — `raw stop` must wait for the selected measurement to become inactive using the existing bounded status logic.

**FR-007** — Reject PPI exercise-start triggers unless official device behavior is later proven to support them.

**FR-008** — `raw fetch` must:

- parse and validate the exact Polar offline-recording path grammar defined in
  [Raw and passive operation contracts](operation-contracts.md);
- fetch exactly one file;
- write atomically;
- reject source/output aliasing and unexpected overwrite;
- return size and SHA-256 metadata.

**FR-009** — Device-facing functions must serialize operations per normalized device identity through `DeviceWorkflowRunner`.

**FR-010** — CLI output must be stable JSON for machine-facing operations. Human-only prose must not be required for parsing.

## Passive collection and deletion

**FR-011** — Add:

```text
polar-ble passive collect \
  --from-date YYYY-MM-DD \
  [--to-date YYYY-MM-DD] \
  [--domain DOMAIN ...] \
  [--existing-file-policy skip|overwrite] \
  [--delete-after-collect]
polar-ble passive cleanup \
  --domain DOMAIN \
  --delete-through YYYY-MM-DD \
  [--dry-run]
```

**FR-012** — Add public asynchronous APIs:

```python
collect_passive_files(..., delete_after_collect=False)
cleanup_passive_files(...)
```

**FR-013** — Passive operations must execute inside a complete PFTP sync lifecycle when required by the device protocol:

```text
initialize/start notifications
→ list/fetch/remove operations
→ terminate/stop notifications
```

The termination status must reflect whether the session completed successfully.
Teardown is attempted after failure and cancellation. A cleanup dry run performs
local verification only and opens no BLE session.

**FR-014** — Passive deletion eligibility requires all of:

- a manifest entry exists for the exact device path;
- the local file exists;
- local size equals the manifest size;
- local SHA-256 equals the manifest SHA-256;
- the manifest’s device identity and domain match the request;
- the logical date satisfies the requested cutoff.

**FR-015** — `delete-after-collect` may delete only records whose current run
status is `fetched` or whose pre-existing local copy is reverified as
`skipped`. It must retain records with unknown logical date and every record on
the latest logical date observed among eligible rows in the successful sync.

**FR-016** — A fetch, decode, manifest, or verification failure must leave the source device file untouched.

**FR-017** — `cleanup` must reject:

- `--domain all`;
- a deletion cutoff equal to or later than the current local date;
- records with unknown logical dates unless explicitly supported by a domain-specific rule;
- files outside the selected domain.

**FR-018** — Every deletion attempt must append an immutable JSONL audit record containing at least:

```text
observed_at
operation_id
schema_version
device_id
domain
logical_date
device_path
local_path
local_sha256
status
deleted_paths
error
dry_run
```

Do not include raw payloads or secrets.

**FR-019** — Stable statuses are:

```text
deleted
dry_run
blocked_unverified
blocked_date
blocked_domain
failed
```

**FR-020** — Passive collection and cleanup must tolerate per-file protocol failures without falsely treating the BLE link as dead; transport failures must still abort the device workflow.

The canonical passive domains, paths, missing-file behavior, sync ordering,
manifest fields, existing-file policy, and exact deletion algorithm are defined
in [Raw and passive operation contracts](operation-contracts.md).

## REC sidecar platform support

**FR-021** — Support decoder build and execution on:

```text
linux/x86_64
linux/aarch64
```

**FR-022** — Pin an architecture-specific Temurin JDK archive name, URL,
version, archive root, executable path, and SHA-256 for each supported
architecture. Normalize `amd64` to `x86_64` and `arm64` to `aarch64`.

**FR-023** — Keep Gradle version and checksum pinned. Reuse one safe extraction and verification path across architectures.

**FR-024** — Decoder manifests must record:

```text
platform
architecture
JDK version
JDK executable SHA-256
Gradle version
SDK commit
adapter digest
runtime-file digests
decoder protocol version
package version
```

**FR-025** — A decoder built for another platform or architecture must report unavailable with an actionable rebuild command.

**FR-026** — Linux aarch64 support must not weaken archive path, symlink, executable, digest, cache-boundary, or rollback checks.

## Protected REC decoding

**FR-027** — Extend the sidecar protocol compatibly to accept an optional recording secret through an ephemeral non-argv channel.

Preferred contract:

```text
Python starts sidecar with a protocol mode flag
→ Python writes one versioned request object to sidecar stdin
→ request may contain the secret
→ sidecar never echoes or persists the secret
→ sidecar emits project-owned JSONL output
```

The request schema, handshake, output envelopes, process limits, and
publication rules are defined in
[REC sidecar and batch protocol](rec-protocol.md).

**FR-028** — Do not pass secrets through:

- positional arguments;
- option values;
- environment variables likely to be logged;
- temporary filenames;
- manifest files;
- build reports.

CLI secret bytes may be read only from a mutually exclusive owner-private
`--secret-file` or `--secret-stdin` source. Secret bytes must never be accepted
as an option value.

**FR-029** — A secret-bearing request must use a project-owned encoding and
validate length and strategy before subprocess execution. Secret models,
provider callbacks, diagnostics, and error paths must be redacted by
construction.

**FR-030** — Support only secret strategies demonstrated by the pinned SDK and private fixture contracts. Unsupported strategies must return a typed unsupported error rather than guess.

**FR-031** — Preserve unencrypted protocol-v1 behavior and add explicit
protocol negotiation. Protocol v2 uses a single request on stdin and is
required for protected decoding; a v1 sidecar must fail cleanly before secret
material is sent.

**FR-032** — Secret-related errors must distinguish at least:

```text
secret_required
secret_invalid
secret_strategy_unsupported
recording_security_unsupported
```

No error may include secret material.

## Batch REC decoding

**FR-033** — Add:

```text
polar-ble rec decode-tree INPUT_DIR [--output-dir DIR]
polar-ble rec decode-manifest MANIFEST.jsonl [--output-dir DIR]
```

**FR-034** — Add corresponding Python APIs:

```python
decode_recording_tree(...)
decode_recording_manifest(...)
```

**FR-035** — `decode-tree` must:

- recursively select regular `*.REC` files;
- not follow symlinks;
- exclude its own output directory;
- preserve relative paths;
- use deterministic ordering;
- produce one validated JSONL output per successfully decoded source;
- produce one `summary.json`;
- continue after per-file decode failures;
- return non-zero when any file failed;
- classify unsupported inputs separately from failed inputs.

Unsupported and failed sources receive no placeholder decoded JSONL; each
still receives exactly one result in the batch summary.

**FR-036** — `decode-manifest` must accept only schema-versioned project-owned
manifest entries with validated root-relative paths, optional expected source
SHA-256 values, and optional opaque `secret_id` provider keys. Absolute paths,
traversal, symlinks, duplicate sources/destinations, unknown fields, and inline
secrets are rejected before the first decode.

**FR-037** — Batch output publication must retain current atomic no-clobber
behavior. The batch preflights all destinations before decoding. An explicit
overwrite option may replace only regular files that validate as project-owned
decoded JSONL, never source REC files or unrelated output-tree contents.

**FR-038** — The batch summary must include:

```text
input_root or manifest
output_root
observed_at
sdk_commit
decoder_version
protocol_version
listed
decoded
unsupported
failed
per-type counts
per-file results
```

The summary also records its schema version, normalized platform and
architecture, deterministic relative paths, per-file source/output SHA-256,
stable error codes, and warnings.

**FR-039** — Batch decoding must support secret resolution without placing a
shared secret into each output. A single secure provider callback or
owner-private secret input may supply secrets to selected records. A provider
is invoked at most once per selected source and receives only a redacted
recording identity.

## Compatibility evidence

**FR-040** — Extend the protected compatibility matrix for Loop Gen 2 and Verity Sense.

**FR-041** — Loop Gen 2 validation must cover:

- discovery, pairing, trust, connect, disconnect, reconnect;
- available types, settings, status, start, stop;
- trigger get/set where device-supported;
- disk-space read;
- raw list, targeted fetch, collection, verification, cleanup dry-run;
- passive listing and collection for every advertised supported domain;
- passive cleanup dry-run and one controlled destructive deletion;
- BPB decode for each claimed schema-backed domain;
- REC decode for every claimed measurement category;
- Linux x86_64 and Linux aarch64 sidecar status where hosts are available.

**FR-042** — Verity Sense validation must cover:

- available recording types and settings;
- start, stop, status, triggers where supported;
- raw retrieval and guarded deletion;
- ACC, GYRO, MAGNETOMETER, PPG, PPI, HR, and SKIN_TEMPERATURE only where fixtures/device behavior support them;
- compressed frame categories claimed by the decoder;
- protected REC decoding where a controlled fixture exists.

Do not claim passive activity/sleep/wellness support for Verity Sense unless the device advertises and passes those contracts.

**FR-043** — Run a two-physical-device concurrency test proving:

- operations for one device serialize;
- independent devices may progress concurrently within a configured global limit;
- cancellation and failure release locks and sessions.

Lock acquisition, global limiting, session ownership, cancellation, and result
ordering follow [Models, errors, and workflow semantics](models-and-errors.md).

**FR-044** — Run controlled reconnect and radio-loss tests. Record unsupported or unvalidated recovery honestly; do not weaken timeouts to force a pass.

**FR-045** — Record compatibility evidence only for behaviors exercised against
controlled fixtures or hardware. Prior observations may inform test design but
are not themselves compatibility evidence.

## Maintainability and refactoring

**FR-046** — Before adding public behavior, identify the owning layer for each responsibility:

```text
commands       argument parsing and process exit behavior
api/collection stable workflow entry points and result composition
device/workflows session ownership, locking, and concurrency
polar          PMD/PFTP/setup protocol behavior
raw_data       raw REC persistence, manifests, and deletion audit
passive_data   passive BPB persistence, manifests, and deletion audit
rec            sidecar protocol, invocation, validation, and batch decode
sdk_tools      explicit SDK/toolchain lifecycle only
```

Command modules must not construct protocol packets, own persistence rules, or duplicate workflow orchestration.

**FR-047** — Refactor repeated device-session wrappers into shared workflow helpers where the abstraction is used by at least two real operations and preserves typed return values.

**FR-048** — Refactor raw and passive verification/deletion logic around shared low-level storage utilities only where their invariants are genuinely identical. Keep domain-specific eligibility and audit models separate.

**FR-049** — Split modules that accumulate unrelated responsibilities. Prefer cohesive modules and explicit dependencies over large command, collector, or sidecar lifecycle files.

**FR-050** — Keep functions narrowly scoped. New or materially changed functions should generally perform one orchestration or validation responsibility and avoid deeply nested control flow.

**FR-051** — Replace repeated stringly typed statuses, modes, and error categories with enums or constrained project-owned models at internal boundaries. Serialize stable string values only at CLI/API boundaries.

**FR-052** — Centralize:

- atomic file publication;
- safe path containment and alias checks;
- SHA-256 streaming;
- JSON/JSONL atomic writes;
- redaction of secrets and sensitive paths;
- subprocess result normalization;
- CLI date and setting parsing where semantics are shared.

Do not create generic helpers that obscure domain invariants or merely save one or two lines.

**FR-053** — Public APIs must not return mutable internal collections that allow callers to violate model invariants. Prefer frozen dataclasses, tuples, mappings, or defensive copies.

**FR-054** — Error handling must preserve the typed subsystem hierarchy in
[Models, errors, and workflow semantics](models-and-errors.md) and avoid broad
exception translation that loses whether a failure was validation, protocol,
transport, storage, security, timeout, cancellation, or unsupported behavior.

**FR-055** — Add docstrings and type annotations to all new public APIs and to non-obvious internal protocol, security, and lifecycle boundaries.

**FR-056** — Tests must target public behavior and stable subsystem contracts. Avoid excessive mocking of internal implementation details that would make safe refactoring difficult.

**FR-057** — Remove dead compatibility shims, unused models, duplicated parsers, and obsolete paths encountered within the modified scope, provided removal does not break documented `0.2.x` public behavior.

**FR-058** — Each implementation phase must include a maintainability review covering:

```text
module ownership
duplicate logic
dependency direction
public versus internal surface
typed errors and models
test coupling
documentation drift
```

The phase is not complete while new behavior leaves a known avoidable duplication or responsibility leak in the touched subsystem.

## SDK provenance, licensing, and protected-data boundaries

**FR-059** — Protobuf message definitions, field numbers, enum definitions,
descriptor sets, and generated language bindings must be generated locally from
the separately obtained and licensed SDK schema inputs. They must not be
manually transcribed, reconstructed, translated, committed, packaged, or
published. Project code may map generated messages into stable project-owned
models only after generation.

`protoc` generation is an explicit user-initiated SDK workflow. Generated
`_pb2.py` modules and descriptor sets remain local cache material governed by
the applicable upstream SDK licence. BPB decoding must use those generated
modules and must not embed copied or reconstructed schema definitions in
project source. When generation is unavailable, decoding reports unavailable;
there is no hand-maintained schema fallback.

**FR-060** — The local SDK install manifest must bind licence acceptance to the
exact staged SDK content and copied licence digest. It records at least:

```text
sdk_commit
source_identity
license_filename
license_sha256
accepted_at
acceptance_method
```

`accepted_at` is UTC. `acceptance_method` is a stable project-owned value such
as `cli_flag`. A changed licence digest, SDK revision, or content-addressed
user-supplied SDK snapshot requires new explicit acceptance. An unchanged
verified cache entry may be reused transactionally. Acceptance records contain
no personal identity, username, hostname, shell history, machine identifier,
telemetry, or public artifact data.

**FR-061** — Every locally built decoder cache entry must include the exact
`Polar_SDK_License.txt` from the resolved SDK source and every required
upstream third-party notice from the compiled source subset. Its manifest must
record each cache-relative notice path and SHA-256 digest. Decoder activation
and verification fail closed if a required licence is absent, a digest differs,
a path escapes the decoder cache, or an unexpected notice file replaces a
recorded file.

The runtime allowlist permits only specifically named licence/notice files in
addition to approved launchers and JARs. These files remain decoder-local cache
material and must not enter the Python wheel, sdist, repository, public CI
artifact or cache, container layer, release asset, or distribution.

**FR-062** — Protected REC decoding must construct the pinned SDK's
secret/security model inside the JVM sidecar and invoke the pinned SDK's
existing REC parser with that model. It supports only security strategies
demonstrably supported by the pinned SDK and private fixture contracts. The
sidecar exposes only project-owned request, response, error, and JSONL
contracts; when the SDK cannot decode a recording, it returns a typed
unsupported or decode error.

The implementation must not independently parse REC headers, metadata, or
payloads, decrypt REC metadata or payloads, decode REC compression, translate the SDK
parser into any language, copy protected parsing logic into project-authored
modules, patch SDK source to expose unsupported behavior, or use Python PMD
secret/decryption code as a REC fallback.

**FR-063** — Each claimed REC record category must have an explicit
project-owned adapter mapping and payload contract. The contract defines public
field names, units, nullability, numeric treatment, timestamp policy, binary
encoding, and stable record type. SDK reflection may be a private extraction
mechanism only; it must not automatically determine public field names,
nesting, or serialized structure.

Unknown SDK fields are ignored or produce a controlled unsupported or
version-mismatch result; they are never serialized opportunistically. An output
contract change requires an explicit protocol or schema-version decision and
private fixture revalidation. Private fixture hashes change only after that
intentional contract decision.

**FR-064** — Restricted SDK-derived and private material must not enter GitHub
Actions artifacts, CI caches, uploaded dependency caches, container or OCI
image layers, Gradle build scans, test reports, coverage bundles, crash dumps,
debug logs, SBOM/provenance bundles, retained temporary CI archives, Git LFS,
release-candidate bundles, release assets, distributions, or Git history.

Public CI uses only synthetic inputs, fake sidecars, and project-authored
fixtures. Protected SDK compilation, real REC/BPB fixtures, hardware tests,
and protected compatibility contracts run only locally or in an explicitly
private environment that uploads no restricted material.

**FR-065** — Real-device fixtures must be consented, disposable, synthetic
where possible, or otherwise approved for their test purpose. Fixtures, decoded
outputs, profile contents, device identifiers, MAC addresses, participant
identifiers, and secrets remain private. Compatibility evidence contains only
the redacted metadata required by this specification; logs and failure reports
contain no raw or decoded participant data.

Protected validation environments document fixture retention and deletion.
Documentation must state that the package is not diagnostic, clinical,
medical-device, life-supporting, or life-critical software, and that data users
remain responsible for applicable privacy and data-protection obligations.
Passive algorithm outputs must not be represented as equivalent to raw waveform
data.
