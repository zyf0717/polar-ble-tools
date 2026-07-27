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

## Maintainability and SDK boundaries

**FR-049** — Decompose REC discovery, process invocation, protocol validation,
payload adaptation, and publication into cohesive modules with explicit
dependencies.

**FR-059** — Generate SDK schemas and bindings locally from separately licensed
inputs only. Generated material remains cache-local and unavailable when
generation cannot be performed; there is no transcribed fallback.

**FR-060** — Before CLI installation, state that proceeding accepts the Polar
BLE SDK licence and require a `y/N` confirmation. Support `-y`/`--yes` for
unattended installation. Require fresh consent for every install/download
invocation, including cache reuse. Calling the explicit Python installation API
also means the caller accepts the licence for that call; no acceptance record
is retained or inherited from a legacy cache.

**FR-061** — Keep SDK source and SDK-derived outputs local and out of project
distributions. Decoder and generated-schema caches do not copy or independently
enforce SDK licence or notice files. Package-managed legacy decoder entries are
not grandfathered; externally managed sidecars are out of scope.

**FR-063** — Each claimed REC category has an explicit project-owned adapter
contract defining names, units, nullability, numeric treatment, timestamps,
binary encoding, and stable record type. Reflection cannot define the public
schema automatically.

FR-027 through FR-032 and FR-062 moved to SPEC-006. FR-033 through FR-039 moved
to SPEC-007. Requirement identifiers remain stable.
