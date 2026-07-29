# SPEC-009 implementation tracker

**Status:** Proposed — experiments and verdict review not started.

Unchecked implementation items are commitments only after the decision matrix
selects their applicable verdict.

## Phase 1 — experiments and decisions

- [ ] **FR-078** — Complete and review every lifecycle decision-matrix row.
- [ ] Baseline current supported Linux package outcomes.
- [ ] Run discovery, resolution, preparation, readiness, reconnect, failure,
  concurrency, and Bleak-version experiments.
- [ ] Record the selected Bleak dependency range.
- [x] Record initial non-reset Loop Gen 2 evidence for structured discovery,
  existing-device preparation, explicit resolution, readiness, cancellation,
  disconnect, same-host/new-process reconnect, and representative PMD/PFTP
  workflows.
- [x] Add a reproducible opt-in, non-reset live harness for structured
  discovery, native reconnect, cancellation cleanup, and recovery.
- [ ] Obtain separately authorized fresh-preparation evidence; no device reset
  or bond removal is authorized by the initial experiment.

## Phase 2 — transport and lifecycle

- [ ] **FR-079, FR-080, FR-081** — Structured discovery, native device
  resolution, and platform-neutral authorized identity.
- [ ] **FR-082, FR-083, FR-084** — Evidence-approved preparation, bounded
  probe, managed lifecycle, and only required OS adapters.
- [ ] **FR-086** — Typed phases, timeouts, cancellation, cleanup, and redacted
  diagnostics.

## Phase 3 — public workflow convergence

- [ ] **FR-085** — Shared connection ownership for PMD, PFTP, raw, passive,
  preparation, probe, and FTU workflows.
- [ ] **FR-087** — Replace `0.4.x` MAC-specific and persistent-connection
  public contracts for `0.5.0`.
- [ ] Remove obsolete subprocess parsing, connection handoff, models,
  arguments, and console entry points selected by the verdict matrix.

## Phase 4 — validation and release

- [ ] **FR-088** — Linux/macOS/Windows automated contracts and controlled Linux
  hardware validation on both supported devices.
- [ ] **FR-089** — Evidence-scoped platform claims and SPEC-005 handoff.
- [ ] Required lint, format, unit, contract, audit, build, packaging, and
  clean-wheel gates.
- [ ] Public documentation, changelog, and `0.5.0` release notes.
