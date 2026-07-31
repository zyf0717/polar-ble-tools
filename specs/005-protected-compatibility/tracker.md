# SPEC-005 tracker

Existing observations may satisfy individual rows only when they conform to
[the evidence contract](evidence-contract.md).

## Existing foundations

- [x] Capability-scoped compatibility observations are documented.
- [x] Opt-in primary-device and limited two-device live probes exist.
- [x] Repository/history restricted-material audit exists.

These checks are partial infrastructure and do not complete FR-040 through
FR-065.

## Phase 1 — evidence contract (deferred)

Policy defaults and reviewer ownership require explicit maintainer or
organizational approval before implementation.

- [ ] Define the private test matrix and redacted evidence schema.
- [ ] Define fixture consent, retention, deletion, and access rules.
- [ ] Define restricted-artifact and release-candidate audit gates.

## Phase 2 — device and radio validation (deferred)

- [ ] **FR-040** — Loop Gen 2 and Verity Sense compatibility matrix.
- [ ] **FR-041** — Controlled Loop Gen 2 coverage.
- [ ] **FR-042** — Controlled Verity Sense coverage without unsupported claims.
- [ ] **FR-043** — Two-device serialization, concurrency, and cancellation.
- [ ] **FR-044** — Controlled reconnect and radio-loss behavior.
- [ ] **FR-045** — Claims backed only by controlled evidence.
- [ ] **FR-091** — macOS and Windows host workflows and physical certification.

## Phase 3 — certification (deferred)

- [ ] **FR-058** — Cross-workstream maintainability review.
- [ ] **FR-064** — Restricted-material exclusion audit.
- [ ] **FR-065** — Private-data and non-medical-positioning controls.
- [ ] Approve the exact release commit and redacted compatibility claims.
