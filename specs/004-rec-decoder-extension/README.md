# SPEC-004: Optional REC decoder extension

**Status:** In progress; lifecycle/provenance slices implemented, batch deferred
**Depends on:** SPEC-003 core BLE tooling

## Scope

SPEC-004 owns optional SDK-backed REC decoder expansion:

- verified Linux x86_64 and aarch64 toolchains;
- content-bound SDK provenance, licence acceptance, and runtime notices;
- secret-aware sidecar protocol negotiation and protected REC decoding;
- deterministic tree and manifest batch decoding (deferred);
- explicit project-owned REC payload adapters and summaries;
- strict restricted-material boundaries.

The existing single-file unprotected decoder remains optional. Core recording,
raw retrieval, passive retrieval, and cleanup do not depend on this spec.

## Documents

- [Requirements](requirements.md)
- [REC sidecar and batch protocol](rec-protocol.md)
- [Models and errors](models-and-errors.md)
- [Implementation plan](implementation-plan.md)
- [Validation](validation.md)
- [Governance](governance.md)
- [Tracker](tracker.md)

## Boundaries

- The decoder is locally built from a separately obtained and licensed SDK.
- No vendor parser, decryptor, schema, or generated binding is reimplemented.
- Protected secrets never enter argv, logs, manifests, filenames, or outputs.
- SDK-derived and private material never enters Git, public CI, distributions,
  caches uploaded by CI, container layers, or release assets.
