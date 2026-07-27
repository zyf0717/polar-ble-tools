# SPEC-004: Optional REC decoder extension

**Status:** Deferred
**Depends on:** SPEC-003 core BLE tooling

See the [deferred tracker](tracker.md).

## Scope

This specification owns optional SDK-backed REC decoder work deferred from
SPEC-003:

- Linux x86_64 and aarch64 toolchain provisioning and verification;
- content-bound SDK provenance, licence acceptance, and decoder-local notices;
- secret-aware sidecar protocol negotiation and protected REC decoding;
- deterministic tree and manifest batch decoding;
- explicit project-owned REC payload adapters and summaries;
- restricted-material controls for SDK-derived and private fixture data.

The source requirements are SPEC-003 FR-021 through FR-039, FR-049, and FR-059
through FR-063 as originally proposed. The detailed protocol draft is retained
in [the original design](../003-ble-operations-extension/rec-protocol.md). These
requirements remain unimplemented until restated and accepted here.

## Boundaries

- The decoder remains optional and locally built.
- Core PMD/PFTP recording and retrieval never depend on Java, Gradle, SDK
  material, generated schemas, private fixtures, or decoder availability.
- No vendor parser is translated or reimplemented in Python.
- No SDK-derived or private material enters Git, public CI, distributions, or
  release assets.

## Completion

SPEC-004 requires its own requirements, protocol contracts, tracker, protected
fixture plan, architecture matrix, and release gate before implementation
begins.
