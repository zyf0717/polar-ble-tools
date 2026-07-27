# Implementation plan

## Phase 1 — recording control and targeted retrieval

1. Establish ownership across command, public API, workflow, PMD/PFTP, and
   storage layers.
2. Expose typed workflow functions around existing control clients.
3. Validate recording types, settings, triggers, and raw paths before opening a
   session where possible.
4. Add thin CLI handlers and stable JSON presentation.
5. Add bounded stop confirmation, disk-space validation, and atomic targeted
   fetch.
6. Export and document the stable Python surface.
7. Test validation, locking, lifecycle, protocol, storage, and CLI contracts.

## Phase 2 — passive collection and guarded deletion

1. Add the complete passive PFTP sync-session boundary.
2. Implement explicit skip/overwrite collection policy.
3. Persist append-only manifests with exact path, size, digest, domain, device,
   and logical-date identity.
4. Implement delete-after-collect with unknown/latest-date retention.
5. Implement local-only cleanup dry-run and guarded destructive cleanup.
6. Audit every deletion attempt with stable statuses.
7. Preserve transport failures while continuing safe per-file protocol failures.
8. Add public APIs, CLI commands, documentation, and contract tests.

## Phase 3 — release hardening

1. Replace raw/passive string statuses with constrained enums.
2. Make public listing and result collections immutable.
3. Centralize atomic writes, JSONL append, and streaming SHA-256.
4. Remove optional-client type ignores from passive dry-run handling.
5. Verify transport failure propagation and mutation-attempt audit behavior.
6. Run lint, formatting, full tests, package build, metadata checks, artifact
   tests, release audit, and clean-wheel smoke tests.
7. Update release documentation and version metadata for `0.3.0`.
