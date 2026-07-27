# SPEC-004 tracker

Implemented checks describe current code. Unchecked items remain required before
the corresponding public compatibility claim.

## Phase 1 — platform and SDK lifecycle

- [ ] **FR-021** — Linux x86_64 and aarch64 build/run support.
- [x] **FR-022** — Pinned architecture-specific JDK metadata and aliases.
- [x] **FR-023** — Pinned Gradle and shared safe extraction.
- [x] **FR-024** — Complete decoder provenance manifests.
- [x] **FR-025** — Actionable platform/architecture mismatch reporting.
- [x] **FR-026** — Equivalent archive, digest, boundary, and rollback safety.
- [x] **FR-059** — Licensed local schema generation only.
- [x] **FR-060** — Fresh per-invocation SDK licence confirmation and `-y`.
- [x] **FR-061** — Local-only SDK material without cache-level licence gates.

## Phase 2 — implementation structure

- [x] **FR-049** — Cohesive REC-module decomposition.

## Phase 3 — adapter certification

- [ ] **FR-063** — Explicit stable payload adapter contracts.

Deferred protected requirements are tracked by SPEC-006. Deferred batch
requirements are tracked by SPEC-007.
