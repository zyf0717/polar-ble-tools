# Implementation plan

## Phase 1 — toolchain and provenance (implemented)

1. Introduce architecture-indexed immutable toolchain descriptors.
2. Add pinned aarch64 JDK provenance and host alias normalization.
3. Generalize provisioning, manifest, verification, activation, and rollback.
4. Add per-invocation licence confirmation and `-y` automation bypass.
5. Bind an exact SDK licence attribution copy to the local decoder manifest
   without creating reusable acceptance state.
6. Add guarded exact, multi-commit, and all-revision SDK cleanup with optional
   corresponding decoder removal.
7. Add synthetic cross-architecture lifecycle tests.

## Phase 2 — architecture certification

1. Build, self-test, and decode the approved private corpus on Linux x86_64.
2. Build and self-test the package-managed decoder on Linux aarch64.
3. Retain only redacted compatibility conclusions in public documentation.

## Phase 3 — explicit adapters

1. Define stable project-owned fields, units, nullability, and timestamp policy
   for each claimed REC category.
2. Replace reflection-derived public payload structure with explicit mappings.
3. Reject or ignore unknown SDK properties without opportunistic output.
4. Validate each adapter against the protected corpus.

Protected protocol work moved to SPEC-006. Batch work moved to SPEC-007.
