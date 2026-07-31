# SPEC-006: Protected REC decoding

**Status:** Deferred; SDK strategy evidence and protected fixtures required
**Depends on:** SPEC-004 single-file decoder

## Scope

SPEC-006 owns optional secret-bearing REC decoding:

- protocol-v2 capability negotiation;
- non-argv secret transport and redacted secret models;
- pinned official-SDK protected parsing with no fallback;
- bounded and redacted sidecar diagnostics;
- protected fixture certification.

Protocol-v1 unprotected decoding remains owned by SPEC-004. Batch orchestration
remains owned by SPEC-007. Compatibility certification follows SPEC-005.

## Documents

- [Requirements](requirements.md)
- [Protocol](protected-protocol.md)
- [Models and errors](models-and-errors.md)
- [Implementation plan](implementation-plan.md)
- [Validation](validation.md)
- [Governance](governance.md)
- [Tracker](tracker.md)

## Boundaries

- Secret material never enters argv, environment variables, filenames,
  manifests, summaries, logs, or public evidence.
- The sidecar constructs and invokes only the pinned SDK security model.
- The package does not implement REC parsing, decompression, or decryption.
- No protected compatibility claim exists until private contracts pass.
