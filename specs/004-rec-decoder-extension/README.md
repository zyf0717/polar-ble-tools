# SPEC-004: Optional REC decoder extension

**Status:** Implementing; lifecycle implemented, certification and adapters open
**Depends on:** SPEC-003 core BLE tooling

## Scope

SPEC-004 owns the package-managed, single-file SDK-backed REC decoder:

- architecture-aware Linux x86_64 and aarch64 toolchain provisioning;
- SDK provenance and a lightweight install-time licence confirmation;
- protocol-v1 sidecar invocation and validated JSONL publication;
- explicit project-owned REC payload adapters;
- strict restricted-material boundaries.

The existing single-file unprotected decoder remains optional. Core recording,
raw retrieval, passive retrieval, and cleanup do not depend on this spec.
Protected decoding is deferred to
[SPEC-006](../006-protected-rec-decoding/README.md). Batch decoding is deferred
to [SPEC-007](../007-rec-batch-decoding/README.md).

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
