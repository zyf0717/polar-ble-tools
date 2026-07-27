# Functional requirements

## Platform and toolchain

**FR-021** — Build and execute the optional sidecar on Linux x86_64 and
Linux aarch64.

**FR-022** — Pin architecture-specific Temurin archive identity, URL, version,
archive root, executable path, and SHA-256. Normalize `amd64` to `x86_64` and
`arm64` to `aarch64`.

**FR-023** — Pin Gradle version and digest and use one safe extraction and
verification implementation across architectures.

**FR-024** — Decoder manifests record platform, architecture, JDK version and
executable digest, Gradle version, SDK commit, adapter digest, runtime-file
digests, protocol version, and package version.

**FR-025** — A sidecar built for another platform or architecture reports
unavailable with an actionable rebuild command.

**FR-026** — aarch64 support retains archive traversal, symlink, executable,
digest, cache-boundary, transaction, and rollback protections.

## Protected REC protocol

**FR-027** — Add a compatible request-on-stdin protocol for optional recording
security material. The sidecar emits only project-owned JSONL output and never
echoes or persists secrets.

**FR-028** — Secrets are accepted only through mutually exclusive owner-private
file or stdin sources. They never appear in positional arguments, option
values, environment variables, filenames, manifests, reports, or diagnostics.

**FR-029** — Secret requests use validated project-owned encoding and immutable,
redacted models. Length and strategy validation occurs before subprocess
execution.

**FR-030** — Support only security strategies proven by the pinned SDK and
private fixtures. Unknown strategies return typed unsupported results.

**FR-031** — Preserve unprotected protocol-v1 behavior. Negotiate protocol-v2
capability before transmitting any secret.

**FR-032** — Stable security error codes distinguish:

```text
secret_required
secret_invalid
secret_strategy_unsupported
recording_security_unsupported
```

No message contains secret material.

## Batch decoding

FR-033 through FR-039 are deferred. They describe a possible future contract,
not current CLI or Python API behavior.

**FR-033** — Provide `rec decode-tree` and `rec decode-manifest` CLI operations.

**FR-034** — Provide corresponding `decode_recording_tree()` and
`decode_recording_manifest()` Python APIs.

**FR-035** — Tree decoding selects regular `*.REC` files without following
symlinks, excludes its output subtree, preserves relative paths, orders inputs
deterministically, publishes one validated JSONL output per success, continues
after per-file failures, and writes one summary.

**FR-036** — Manifest decoding accepts only a strict schema-versioned
project-owned format with root-relative paths, optional expected SHA-256, and
opaque provider keys. Reject traversal, absolute paths, symlinks, duplicates,
unknown fields, and inline secrets before decoding.

**FR-037** — Preflight every destination. Default to atomic no-clobber
publication; explicit overwrite may replace only validated project-owned
decoded outputs, never REC sources or unrelated files.

**FR-038** — Batch summaries are versioned and contain deterministic relative
paths, environment/protocol provenance, counts, per-type counts, per-file
results, source/output digests, stable codes, and warnings.

**FR-039** — Resolve selected secrets through a secure provider invoked at most
once per source with only a redacted recording identity.

## Maintainability and SDK boundaries

**FR-049** — Decompose REC discovery, process invocation, protocol validation,
payload adaptation, and publication into cohesive modules with explicit
dependencies.

**FR-059** — Generate SDK schemas and bindings locally from separately licensed
inputs only. Generated material remains cache-local and unavailable when
generation cannot be performed; there is no transcribed fallback.

**FR-060** — Before CLI installation, state that proceeding accepts the Polar
BLE SDK licence and require a `y/N` confirmation. Support `-y`/`--yes` for
unattended installation. Calling the explicit Python installation API also
means the caller accepts the licence; no acceptance record is required.

**FR-061** — Keep SDK source and SDK-derived outputs local and out of project
distributions. Decoder and generated-schema caches do not copy or independently
enforce SDK licence or notice files.

**FR-062** — Protected REC decoding constructs the SDK security model inside
the JVM sidecar and invokes only the pinned official parser. No project-authored
REC metadata parser, payload parser, decompressor, decryptor, SDK patch, or
Python fallback is permitted.

**FR-063** — Each claimed REC category has an explicit project-owned adapter
contract defining names, units, nullability, numeric treatment, timestamps,
binary encoding, and stable record type. Reflection cannot define the public
schema automatically.
