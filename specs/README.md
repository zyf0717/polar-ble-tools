# Specifications

This directory contains development-only design contracts, implementation
plans, evidence requirements, and completion records. Specifications guide
work on `dev`.

The public sources of truth remain:

- `docs/architecture.md` for package and dependency boundaries;
- `docs/development.md` for development workflows;
- `docs/compatibility.md` for evidence-backed support claims.

A specification may strengthen those constraints while it is active, but must
not silently redefine them. Accepted public behavior must be reflected in the
applicable public documentation before release.

## Numbering

Specification identifiers are stable three-digit numbers. Gaps are allowed and
completed specifications are not renumbered.

- `SPEC-000` is reserved for a future versioned specification-governance
  contract if this index becomes insufficient.
- `SPEC-001` and `SPEC-002` are unassigned; their absence does not imply missing
  repository content.
- New work uses the next unassigned identifier.

## Lifecycle

Each specification README declares its status, scope, milestone when
applicable, dependencies, and boundaries. Supporting documents should cover
requirements, implementation, validation, governance, and tracking when those
concerns are material.

Use these lifecycle states:

1. **Proposed** — scope and requirements are under review.
2. **Accepted** — boundaries and acceptance criteria are approved.
3. **Implementing** — code, tests, and documentation are in progress.
4. **Implemented** — validation and definition-of-done requirements are met.
5. **Deferred** — intentionally paused pending an explicit prerequisite or
   product decision; it is not an active implementation commitment.
6. **Superseded** — a referenced successor owns the active contract.

Specification changes remain on `dev`.

## Index

| Specification | Status | Scope |
| --- | --- | --- |
| [SPEC-003](003-ble-operations-extension/README.md) | Implemented | Core BLE operations |
| [SPEC-004](004-rec-decoder-extension/README.md) | Implementing | Single-file structured REC decoding |
| [SPEC-005](005-protected-compatibility/README.md) | Deferred | Protected compatibility certification |
| [SPEC-006](006-protected-rec-decoding/README.md) | Deferred | Protected REC decoding |
| [SPEC-007](007-rec-batch-decoding/README.md) | Deferred | REC batch decoding |
| [SPEC-008](008-bpb-decoding/README.md) | Implemented | Official-schema BPB decoding |
| [SPEC-009](009-bleak-platform-migration/README.md) | Implementing | Bleak-first operations and cross-platform readiness |
