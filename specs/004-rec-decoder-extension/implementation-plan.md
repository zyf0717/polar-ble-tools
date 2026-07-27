# Implementation plan

## Phase 1 — toolchain and provenance

1. Introduce architecture-indexed immutable toolchain descriptors.
2. Add pinned aarch64 JDK provenance and host alias normalization.
3. Generalize provisioning, manifest, verification, activation, and rollback.
4. Bind SDK acceptance and decoder-local licence/notices to staged content.
5. Add synthetic cross-architecture lifecycle tests.

## Phase 2 — protected sidecar protocol

1. Finalize protocol-v2 negotiation and bounded request/status schemas.
2. Add owner-private secret sources and redacted secret/provider models.
3. Implement stdin request transport and bounded concurrent stream draining.
4. Construct the pinned SDK security model only in the sidecar.
5. Preserve v1 unprotected behavior.
6. Add canary leakage, timeout, malformed-output, and process cleanup tests.

## Phase 3 — batch decoding and adapters

1. Separate discovery, manifest validation, invocation, adaptation, and output
   publication.
2. Implement deterministic tree discovery and strict manifest preflight.
3. Define explicit adapter contracts for every claimed category.
4. Add atomic output and constrained overwrite handling.
5. Add immutable batch summaries and thin CLI/API wrappers.
6. Validate every claimed category against the protected corpus.
