# SPEC-003 implementation tracker

**Status:** Complete — implemented SPEC-003 code contract.

## Phase 1 — recording control and retrieval

- [x] **FR-001–010** — Public recording-control, status, trigger, disk-space,
  targeted fetch, workflow serialization, and stable CLI contracts.
- [x] **FR-046–047** — Layer ownership and shared typed workflow boundaries.

## Phase 2 — passive collection and cleanup

- [x] **FR-011–020** — Passive list/collect/cleanup, sync lifecycle,
  verification, retention, deletion audit, statuses, and transport handling.
- [x] **FR-048** — Shared low-level storage mechanics with separate domain
  policy.

## Phase 3 — release hardening

- [x] **FR-050–057** — Narrow functions, constrained models, centralized shared
  helpers, immutable collections, typed failures, annotations, contract tests,
  and in-scope dead-path cleanup.
- [x] Full tests, lint, formatting, build, metadata checks, package-content
  tests, release audit, and clean-wheel smoke test.
- [x] Package and documentation version updated to `0.3.0`.

## Release follow-ups — outside SPEC-003 completion

- [ ] Re-run the private hardware smoke matrix for the exact release commit.
- [ ] Publish through the approved TestPyPI/PyPI workflow.

SPEC-004 and SPEC-005 have separate trackers and do not block completion of the
implemented SPEC-003 code contract.
