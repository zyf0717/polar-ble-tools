# Single-file REC sidecar protocol

This document describes the current package-managed protocol-v1 decoder
contract. Protected protocol-v2 behavior is owned by SPEC-006. Tree and manifest
batch behavior is owned by SPEC-007.

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

An offline build may reuse only a complete descriptor-verified cached
toolchain. It performs no network request and returns an actionable typed error
when a required artifact is absent.

The active decoder manifest records:

```text
manifest_version
decoder_protocol_version
sdk_commit
decoder_version
polar_ble_tools_version
platform
architecture
java_version
java_archive_sha256
gradle_version
gradle_archive_sha256
toolchain_descriptor_sha256
adapter_source_sha256
verified
verification_level
executable_relative_path
executable_sha256
runtime_files
runtime
```

Every relative path resolves inside its applicable configured cache root.
Decoder files remain inside the per-commit decoder entry; the JDK remains
inside the architecture-specific toolchain cache. Every regular decoder runtime
file is allow-listed and hashed. Runtime platform, architecture, executable,
JDK digest, sidecar version handshake, SDK commit, and protocol version are
reverified before decode. A mismatch reports unavailable or verification
failure with `polar-ble sdk decoder build` as remediation; it never silently
selects another decoder.

## SDK licence confirmation

Every SDK install/download CLI invocation states that proceeding accepts the
Polar BLE SDK licence and uses a `y/N` confirmation, including cache reuse.
`-y`/`--yes` proceeds non-interactively. Each explicit Python installation API
call implies fresh acceptance by the caller.

Acceptance is not persisted or bound to SDK content. Decoder and
generated-schema cache entries do not copy or validate separate SDK licence or
notice files. SDK source and SDK-derived outputs remain local and excluded from
Git, Python distributions, public CI artifacts or caches, container layers, and
release assets.

Package-managed decoder entries carrying the former licence-material manifest
contract are rejected with a rebuild remediation. Externally managed sidecars
are outside this package's lifecycle and compatibility scope.

## Protocol-v1 invocation

The Python caller verifies `version` before decoding and invokes:

```text
<decoder> decode --input <source.REC> --output <staged.jsonl> --protocol 1
```

Protocol-v1 carries no recording secret. Encrypted or otherwise protected
recordings are unsupported. The sidecar returns one bounded JSON status object
on stdout; stderr is bounded diagnostic text.

Subprocesses use argument arrays, a positive timeout, concurrent bounded
stdout/stderr drains, and a new process session on POSIX. Timeout terminates the
complete process group, waits a bounded grace period, then kills it if required.
A timeout publishes no output.

The current runtime environment inherits the invoking process environment and
overrides `JAVA_HOME` and `PATH` for the pinned JDK. The stricter environment
and secret-redaction contract required for protected decoding belongs to
SPEC-006.

## Official SDK parser boundary

The JVM sidecar calls the pinned official SDK REC parser. It may adapt SDK
parser results to project-owned output, but it must not independently parse REC
headers, metadata, or payloads, decode compression, translate the parser into
another implementation, copy parsing logic into project-authored code, patch
SDK source, or use a Python fallback.

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
  "protocol_version": 1,
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

`timestamp_ns` may be null where validated SDK semantics do not provide an
absolute timestamp. Payloads contain JSON scalars, arrays, and objects only.
The sidecar encodes non-finite SDK numbers as null with a warning; Python
validation rejects non-standard JSON numeric constants.

Summary:

```json
{
  "type": "summary",
  "record_count": 0,
  "record_types": {},
  "warnings": []
}
```

Python validates regular-file and symlink safety, per-line byte limits, UTF-8,
finite JSON values, row order, record envelopes, source digest, SDK provenance,
protocol version, count totals, per-type totals, warnings, and absence of rows
after the summary. Validation happens before publication.

Output is created in a private staging directory under the destination parent.
No-clobber publication is atomic. Overwrite uses atomic replacement only after
the existing destination is confirmed to be a regular project-owned decoded
JSONL file. Source and destination aliasing is always rejected.

## Explicit payload adapters

FR-063 remains open. The current adapter explicitly maps REC measurement types
and timestamp policy, but discovers iterable SDK result properties through
reflection and emits reflected sample objects. These outputs are experimental
and do not establish stable per-category payload contracts.

Completion requires a versioned project-owned adapter contract for each claimed
category:

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

SDK property names, reflection order, and newly discovered properties must not
determine the completed public schema. Unknown SDK properties are ignored or
produce a controlled unsupported/contract-mismatch result.
