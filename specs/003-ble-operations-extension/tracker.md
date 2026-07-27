# SPEC-003 implementation tracker

Track implementation against [Functional requirements](requirements.md) and
[Implementation plan](implementation-plan.md). Check an item only when its
implementation, contract tests, and required documentation are complete.

## Phase 1 — recording-control API, CLI, and boundary refactor

- [x] **FR-001** — Provide the high-level async raw-recording APIs.
- [x] **FR-002** — Export and document the public APIs, including the top-level facade where appropriate.
- [x] **FR-003** — Provide the `polar-ble raw` CLI operations.
- [x] **FR-004** — Reuse the established clients, workflow runner, and project-owned models; do not construct PMD packets in commands.
- [x] **FR-005** — Validate measurement types and settings before device-session acquisition where possible.
- [x] **FR-006** — Make `raw stop` wait for bounded inactive status.
- [x] **FR-007** — Reject unsupported PPI exercise-start triggers.
- [x] **FR-008** — Implement grammar-validated, atomic, no-alias/no-clobber single-file raw fetch with size and SHA-256 metadata.
- [x] **FR-009** — Serialize all device-facing work by normalized device identity through `DeviceWorkflowRunner`.
- [x] **FR-010** — Emit stable machine-readable JSON from CLI operations.
- [x] **FR-046** — Keep each responsibility in its owning layer and preserve command-module boundaries.
- [x] **FR-047** — Consolidate repeated device-session wrappers used by at least two operations without weakening typed returns.
- [x] **FR-050** — Keep new or materially changed functions narrow and shallowly nested.
- [x] **FR-051** — Replace repeated stringly typed statuses, modes, and errors with constrained project-owned models.
- [x] **FR-052** — Centralize shared atomic publication and JSONL utilities while retaining domain-specific invariants.
- [x] **FR-053** — Prevent public APIs from returning mutable internal collections.
- [x] **FR-054** — Preserve typed transport, protocol, storage, timeout, and unsupported-operation failures.
- [x] **FR-055** — Add docstrings and annotations to new public APIs and non-obvious internal boundaries.
- [x] **FR-056** — Test public behavior and stable contracts without excessive implementation-detail mocking.
- [x] **FR-057** — Remove obsolete in-scope shims, models, parsers, and paths without breaking documented 0.2.x behavior.

## Phase 2 — passive deletion safety and storage refactor

- [x] **FR-011** — Provide `passive collect` and `passive cleanup` CLI operations and options.
- [x] **FR-012** — Provide public async collection and cleanup APIs.
- [x] **FR-013** — Implement the required PFTP sync lifecycle, including failure/cancellation teardown and local-only cleanup dry runs.
- [x] **FR-014** — Gate deletion on exact manifest, file, size, digest, device, domain, and date verification.
- [x] **FR-015** — Restrict delete-after-collect eligibility and retain unknown/latest logical-date records.
- [x] **FR-016** — Preserve source device files after fetch, decode, manifest, or verification failure.
- [x] **FR-017** — Reject unsafe cleanup domains, cutoffs, unknown dates, and out-of-domain files.
- [x] **FR-018** — Append immutable, secret-free JSONL audit records for every deletion attempt.
- [x] **FR-019** — Use the specified stable passive-deletion statuses.
- [x] **FR-020** — Continue across per-file protocol failures while aborting on transport failures.
- [x] **FR-048** — Share raw/passive storage utilities only where invariants truly match; retain domain-specific models and eligibility.

## Deferred follow-on specifications

- [ ] [SPEC-004](../004-rec-decoder-extension/README.md) — Optional REC
  decoder platform, protected decoding, batch decoding, and adapter contracts
  (transferred FR-021–039, FR-049, and FR-059–063).
- [ ] [SPEC-005](../005-protected-compatibility/README.md) — Protected
  hardware, fixture, privacy, and release evidence (transferred FR-040–045,
  FR-058, and FR-064–065).

These items are not completion gates for SPEC-003.

## Release handoff

- [x] Run lint, formatting, full tests, build, metadata validation, package
  content tests, release audit, and clean-wheel smoke tests.
- [ ] Re-run the private hardware smoke matrix for the exact release commit.
- [ ] Select the release version and update release metadata.
- [ ] Build once from the validated commit and perform the TestPyPI/PyPI
  promotion when the maintainer authorizes publication.
