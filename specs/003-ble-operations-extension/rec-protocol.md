# REC sidecar and batch protocol

This document makes FR-021 through FR-039 normative. The protocol is
project-owned; SDK objects remain behind the sidecar boundary.

## Platform and toolchain descriptors

Host normalization maps:

```text
Linux                         → linux
AMD64, amd64, x86_64          → x86_64
AArch64, arm64, aarch64       → aarch64
```

All other platform/architecture pairs are unsupported. Toolchain selection is
an immutable lookup keyed by `(platform, architecture)` and contains:

```text
jdk_version
jdk_archive_name
jdk_url
jdk_sha256
jdk_archive_root
java_relative_path
gradle_version
gradle_archive_name
gradle_url
gradle_sha256
```

Archive download, checksum verification, safe extraction, executable
verification, and staged promotion use one implementation for both
architectures. Archive members are rejected if absolute, parent-traversing,
device nodes, unsafe links, or outside the expected archive root.

An offline build may reuse only a complete checksum-verified cached toolchain.
It performs no network request and returns an actionable typed error when a
required artifact is absent.

The active decoder manifest is immutable after promotion and includes the
fields in FR-024 plus:

```text
manifest_version
verified
verification_level
executable_relative_path
executable_sha256
runtime_files
java_relative_cache_path
toolchain_descriptor_digest
```

Every relative path resolves inside the decoder cache. Every regular runtime
file is allow-listed and hashed. Runtime platform, architecture, executable,
JDK digest, sidecar version handshake, SDK commit, and protocol version are
reverified before decode. A mismatch reports unavailable or verification
failure with `polar-ble sdk decoder build` as remediation; it never silently
selects another decoder.

## SDK licence and notice material

Decoder build copies the exact `Polar_SDK_License.txt` from the resolved SDK
source into the staged decoder cache entry. It also copies every upstream
third-party notice required by the compiled SDK source subset. The build records
each file as a manifest item:

```text
kind                 license | notice
cache_relative_path
sha256
source_identity
```

The licence and notice paths are fixed, specifically named allowlist entries.
They must be regular, non-symlink files that resolve inside the staged decoder
cache. The runtime allowlist otherwise contains only approved launchers and
JARs. The manifest contains the SHA-256 of every copied licence/notice file and
the exact resolved SDK source identity used to obtain it.

Activation, verification, and status fail closed when `Polar_SDK_License.txt`
is absent, a required notice is absent, a recorded digest differs, a recorded
path escapes the cache, or an unexpected replacement notice file appears. A
failed build or activation preserves the last verified active decoder. Removing
a decoder cache entry removes its decoder-local licence and notice copies with
that entry.

These files are local decoder-cache material. They are not copied into Git, the
Python wheel or sdist, public CI artifacts or caches, container layers, release
assets, or distributions.

## Protocol versions

Protocol v1 remains the unencrypted command-line protocol used by existing
`0.2.x` sidecars. Protocol v2 is the request-on-stdin protocol and is required
for secret-bearing operations.

The Python caller chooses a protocol only after a verified `version` handshake:

- an unencrypted single-file decode may use v1 or v2;
- a protected decode requires v2;
- a v1 sidecar receiving a protected request is reported as
  `recording_security_unsupported`;
- version mismatch never falls back after a request has been sent.

Protocol-v1 handshakes retain their singular `protocol_version` integer.
Protocol-v2 handshakes expose a sorted `protocol_versions` array. Python
normalizes both forms into the public `protocol_versions` tuple. Common
handshake fields are:

```text
status
decoder_version
sdk_commit
```

Protocol-v2 also returns `capabilities`, which explicitly identifies
protected-decode strategies and batch-request support. Capability absence is
unsupported, not false evidence of support.

## Official SDK parser boundary

The JVM sidecar constructs the pinned SDK's own recording secret/security model
from the project-owned request only inside the JVM process. It then calls the
pinned SDK's existing REC parser with that model. Security strategies are
enabled only after the pinned SDK and protected fixture contract demonstrate
support. If the SDK cannot parse the recording or expose the requested
strategy, the sidecar returns a stable project-owned unsupported or decode
error.

The sidecar may adapt SDK parser results to project-owned output, but it must
not independently parse REC headers, metadata, or payloads, decrypt metadata or payloads,
decode compression, translate the parser into Python, Kotlin, Swift, Rust, C,
or another implementation, copy protected parsing logic into project-authored
code, patch SDK source, or use Python PMD secret/decryption behavior as a REC
fallback. Reflection, when unavoidable, is limited to private SDK result
extraction and does not implement parsing or decryption.

## Protocol-v2 request

The sidecar is started with an argument array equivalent to:

```text
<decoder> request --protocol 2
```

Input path, output path, and secret are not placed in argv. Python writes one
UTF-8 JSON request followed by a newline, closes stdin, and reads bounded
stdout/stderr concurrently.

Request schema:

```json
{
  "protocol_version": 2,
  "request_id": "opaque-random-id",
  "operation": "decode",
  "source": {
    "path": "/resolved/input.REC",
    "sha256": "64 lowercase hexadecimal characters"
  },
  "destination": {
    "path": "/private/staging/output.jsonl"
  },
  "secret": {
    "strategy": "vendor-validated-project-value",
    "encoding": "base64",
    "key": "base64 bytes"
  }
}
```

`secret` is omitted for unprotected input. Unknown top-level fields,
unsupported operations, invalid digests, malformed base64, duplicate JSON
keys, invalid UTF-8, and over-limit requests are protocol errors. Secret
strategy and decoded key length are validated by Python before process start
and independently by the sidecar before SDK invocation.

The request object is held only in memory. It is never written to a manifest,
temporary request file, exception, debug representation, or diagnostic.
Request and response byte limits are fixed project constants and are tested;
they are not caller-controlled.

## Secret sources and redaction

CLI secret sources are mutually exclusive:

```text
--secret-file PATH
--secret-stdin
```

Secret bytes are never accepted directly as an option value. A secret file is
a regular, non-symlink file with owner-only permissions on POSIX hosts. The
strategy is non-secret metadata and may be supplied separately. Reading from
stdin happens before the sidecar starts; interactive prompting may be provided
only when stdin is a TTY.

Python accepts an immutable redacted secret model or a provider callback:

```python
SecretProvider = Callable[[RecordingIdentity], RecordingSecret | None]
```

The model's `repr`, `str`, serialization, equality diagnostics, and exceptions
never expose key bytes. Provider exceptions are security errors with redacted
record identity. The provider is called at most once per selected source.

After the request is written, Python releases its reference to serialized
secret material as soon as practical. The specification does not claim secure
memory erasure from managed runtimes.

All sidecar stdout, stderr, status objects, warnings, exception messages, and
batch summaries pass through a redaction guard. Tests use distinctive canary
secrets and assert their raw, hexadecimal, and base64 representations are
absent.

## Sidecar process lifecycle

Subprocesses use argument arrays, `shell=False`, a minimal explicit
environment, bounded stdout/stderr drains, and a positive timeout. Environment
variables contain toolchain configuration only and no secret.

On timeout or cancellation, Python terminates the complete sidecar process
group, waits a bounded grace period, then kills it if required. Reader tasks or
threads must finish before returning. A timeout publishes no output.

For a process that exits normally, exit status and the final stdout status
object must agree. Timeout, cancellation, spawn failure, and malformed stdout
are synthesized as typed Python errors. A sidecar error status contains a
stable project-owned code, never an SDK exception class:

```text
usage
protocol_incompatible
unsupported_recording
secret_required
secret_invalid
secret_strategy_unsupported
recording_security_unsupported
decode_failed
timeout
license_notice_missing
license_notice_mismatch
sdk_output_contract_mismatch
```

Unknown codes are protocol errors. Stderr is diagnostic only, size-limited,
redacted, and never parsed as the authoritative result.

## Decoded JSONL contract

Successful output is UTF-8 JSONL in this exact order:

1. one `header` row;
2. zero or more `record` rows;
3. one `summary` row;
4. end of file.

Header:

```json
{
  "type": "header",
  "protocol_version": 2,
  "sdk_commit": "40 lowercase hexadecimal characters",
  "decoder_version": "project version",
  "source_sha256": "64 lowercase hexadecimal characters"
}
```

Record:

```json
{
  "type": "record",
  "record_type": "project_owned_snake_case",
  "timestamp_ns": 0,
  "payload": {}
}
```

`timestamp_ns` may be null only where validated SDK semantics do not provide an
absolute timestamp. Payloads contain JSON scalars, arrays, and objects only.
Non-finite numbers are encoded as null with a warning. Binary values use an
object containing `encoding: "base64"` and `data`.

Summary:

```json
{
  "type": "summary",
  "record_count": 0,
  "record_types": {},
  "warnings": []
}
```

`protocol_version` equals the selected supported protocol; the example shows
v2. Python validates regular-file and symlink safety, per-line byte limits, UTF-8,
finite JSON values, row order, record envelopes, source digest, SDK provenance,
protocol version, count totals, per-type totals, warnings, and absence of rows
after the summary. Validation happens before publication.

Output is created in a private staging directory under the destination parent.
No-clobber publication is atomic. Overwrite uses atomic replacement only after
the existing destination is confirmed to be a regular project-owned decoded
JSONL file. Source and destination aliasing is always rejected.

## Explicit payload adapters and output versioning

Each supported REC category has a versioned project-owned adapter contract.
For every category it declares:

```text
record_type
public fields and nesting
units
nullability
integer/float and non-finite-number treatment
timestamp policy
binary encoding
warnings and unsupported conditions
```

The adapter maps private SDK parser results into this declared contract. SDK
class names, property names, reflection order, and newly discovered properties
must not determine JSONL field names, nesting, or output shape. Unknown SDK
properties are ignored or result in controlled `sdk_output_contract_mismatch`
or unsupported behavior; they are never emitted opportunistically.

Any public adapter change requires an intentional decoder protocol or output
schema-version decision. The change updates the relevant project-owned mapping,
fixture expectations, and private fixture hashes together. Private fixture
hashes must not be regenerated merely to accept an unreviewed SDK output change.

## Decode-manifest input

The manifest is UTF-8, newline-terminated, project-owned JSONL. Each
non-empty row has:

```json
{
  "schema_version": 1,
  "source": "relative/path/ACC.REC",
  "source_sha256": "optional lowercase SHA-256",
  "secret_id": "optional opaque provider key"
}
```

Rules:

- `source` is relative to the caller-supplied manifest root;
- absolute paths, empty segments, `.`/`..`, symlinks, non-regular files, and
  non-`.REC` suffixes are rejected;
- resolved sources remain inside the manifest root;
- duplicate sources, duplicate derived destinations, unknown fields, and
  unsupported schema versions fail manifest validation before decoding;
- `source_sha256`, when present, is checked before invoking the sidecar;
- `secret_id` is opaque and never contains secret material;
- inline secret fields are forbidden.

A malformed completed row fails the operation before any decode. A final
non-newline-terminated row is a malformed manifest, not an ignorable partial
entry.

## Tree discovery and output mapping

Tree discovery resolves the input and output roots once. It walks without
following directory symlinks, selects readable regular files whose suffix is
`.REC` case-insensitively, excludes the resolved output subtree, and sorts by
relative POSIX path.

For both tree and manifest modes:

```text
relative/path/ACC.REC → <output-root>/relative/path/ACC.jsonl
```

Before decoding, the batch preflights source/output aliasing, duplicate
destinations, output-root containment, parent-directory safety, and all
no-clobber conflicts. Without overwrite, any existing destination or summary
aborts before the first sidecar invocation.

With overwrite, only regular decoded JSONL destinations that pass the
project-owned header/summary validation may be replaced. The operation never
removes unrelated or stale files from the output tree.

## Batch execution and summary

Every selected source receives exactly one per-file result. Successful sources
receive a validated JSONL output. Unsupported and failed sources receive no
placeholder decoded JSONL; their typed outcomes appear in `summary.json`.

The default implementation decodes sequentially. A future bounded concurrency
option may run independent sidecars concurrently, but publication and summary
ordering remain relative-path order and secret-provider calls remain bounded.

Per-file result:

```text
status              decoded | unsupported | failed
source
relative_path
output
source_sha256
output_sha256
record_type
record_count
record_types
warnings
error_code
error
```

Paths in serialized batch results are relative to the declared roots unless
the caller explicitly requests resolved paths. `error` is redacted and
human-readable; automation uses `status` and `error_code`.

`summary.json` is schema-versioned, deterministically ordered, and atomically
published after all selected sources finish. It contains FR-038 fields plus
`schema_version`, `summary_path`, `source_sha256`/`output_sha256` per file, and
the normalized architecture.

Unsupported inputs do not count as failed. CLI exit status is zero when
`failed == 0`, including an unsupported-only batch, and one when any file
failed. Preflight or summary-publication failure returns one and is an
operation-level failure.
