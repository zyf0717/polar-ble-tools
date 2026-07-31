# SPEC-009 implementation tracker

**Status:** Implementing — product and automated gates complete locally;
exact-commit CI, maintainer diff review, and protected hardware/release gates
remain.

Unchecked implementation items are commitments only after the decision matrix
selects their applicable verdict.

## Phase 1 — experiments and decisions

- [x] **FR-078** — Complete and review every lifecycle decision-matrix row.
- [x] Baseline current supported Linux package outcomes.
- [x] Run discovery, resolution, preparation, readiness, reconnect, failure,
  concurrency, and Bleak-version experiments.
- [x] Record `bleak>=1.0,<3.1` after isolated full unit/contract passes on
  Bleak 1.0.0 and current PyPI release 3.0.2; hardware evidence uses 3.0.2.
- [x] Record initial non-reset Loop Gen 2 evidence for structured discovery,
  existing-device preparation, explicit resolution, readiness, cancellation,
  disconnect, same-host/new-process reconnect, and representative PMD/PFTP
  workflows.
- [x] Add a reproducible opt-in, non-reset live harness for structured
  discovery, native reconnect, cancellation cleanup, and recovery.
- [x] Add downstream Loop Gen 2 evidence and an opt-in harness for FTU/config
  reads, PMD/PFTP status, ACC start/stop, verified REC retrieval, and eligible
  cleanup dry-run.
- [x] Apply the maintainer-approved
  `docs/loop-gen2-ftu-profile.example.json` input and verify FTU completion
  plus every declared physical/settings field.
- [x] Obtain separately authorized fresh Loop Gen 2 preparation evidence after
  device reset and exact host-record removal: Bleak required a BlueZ
  authentication agent, then paired, verified PMD/PFTP, disconnected, and
  persisted across new-client and new-process reconnects.
- [x] Re-establish FTU from the tracked Loop Gen 2 documentation profile after
  reset and pass the Bleak FTU/PMD/PFTP/ACC/retrieval/verification and cleanup
  dry-run E2E from the freshly paired state.
- [x] Reapply the Loop Gen 2 profile twice after FTU completion and verify all
  14 declared fields after each application. Treat this as a repeat-safe
  semantic outcome, not no-write idempotence.
- [x] Repeat applicable evidence on an authorized Verity Sense after exact
  Bleak `unpair()`: reproduce the missing-agent failure, pass agent-assisted
  preparation, and pass agent-free reconnect, cancellation recovery, and
  read-only PMD/PFTP workflows.
- [x] Repeat Verity Sense preparation after a documented device factory reset:
  reconfirm the Linux agent requirement, pass agent-assisted pairing and
  agent-free new-process reconnect, and verify the Loop-style FTU marker
  remains absent.
- [x] Attempt the tracked FTU profile on factory-reset Verity Sense; record two
  bounded PFTP response timeouts, a present physical configuration, incomplete
  FTU, clean disconnects, and stop further writes pending protocol diagnosis.
- [x] Reclassify that attempt as an inapplicable Loop-style FTU workflow:
  Verity setup uses wear location and default pool length, current settings
  expose only wear location, and no pool-length write contract is verified.
- [x] Split the tracked examples into Loop Gen 2 and wear-location-only Verity
  Sense FTU profiles; add device-family dispatch and tests that prevent routing
  the Verity sample through Loop physical-data writes.
- [x] Apply and independently read-back verify the Verity sample's
  `UPPER_ARM_LEFT` component through Bleak-backed `UDEVSET.BPB` settings.
- [x] Identify the protected `/U/USENSET.BPB` pool-settings candidate, record
  its `OPERATION_NOT_PERMITTED` read result, and stop before an unverified
  pool-length write.
- [x] Pass Verity PMD/PFTP readiness and ACC
  start/stop/retrieval/verification/cleanup-dry-run E2E despite the absent
  Loop-style FTU marker.
- [x] Define and contract-test device-specific Verity FTU: runtime
  system/local-time setup followed by the generated `UDEVSET.BPB`
  wear-location patch, with no Loop physical-data or user-identifier writes.
- [x] Pass the narrowed tracked Verity profile through public CLI apply and
  independent Bleak read-back; add a family-gated reproducible live test.
- [x] Validate Verity system/local time update and independent read-back through
  Bleak: both writes succeeded without fallback, timezone offset was retained,
  and the clock advanced across a new managed session.
- [x] **FR-090** — Integrate the verified time and wear-location operations as
  one protocol-client path; pass both public Python and CLI application with
  independent time/location read-back on authorized Verity hardware.
- [x] Prove deterministic same-device serialization and distinct-device
  overlap; record the current string-address concurrent-scan failure and pass
  three shared-scan/native-object simultaneous PMD/PFTP cycles on both
  configured devices.
- [x] Cancel one of two simultaneous native connects, verify the other reaches
  readiness, clean both clients, and pass concurrent PMD/PFTP recovery on both
  configured devices.
- [x] Classify Verity pool length as unsupported/deferred for `0.5.0`; do not
  infer a pool-setting write path from schemas alone.
- [x] Design and contract-test the narrow Linux authentication-agent boundary;
  fresh Loop Gen 2 and factory-reset Verity Sense preparation are
  Bleak-plus-OS-adapter candidates.

## Phase 2 — transport and lifecycle

- [x] **FR-079, FR-080, FR-081** — Structured discovery, native device
  resolution, and platform-neutral authorized identity.
- [x] **FR-082, FR-083, FR-084** — Evidence-approved preparation, bounded
  probe, managed lifecycle, and only required OS adapters.
- [x] **FR-086** — Typed phases, timeouts, cancellation, cleanup, and redacted
  diagnostics.

## Phase 3 — public workflow convergence

- [x] **FR-085** — Shared connection ownership for PMD, PFTP, raw, passive,
  preparation, probe, and FTU workflows.
- [x] **FR-087** — Replace `0.4.x` MAC-specific and persistent-connection
  public contracts for `0.5.0`.
- [x] Remove obsolete subprocess parsing, connection handoff, models,
  arguments, and console entry points selected by the verdict matrix.

## Phase 4 — validation and release

- [ ] **FR-088** — Linux/macOS/Windows automated contracts and controlled Linux
  hardware validation on both supported devices.
- [x] **FR-089** — Evidence-scoped platform claims and SPEC-005 handoff.
- [x] Required lint, format, unit, contract, audit, build, packaging, and
  clean-wheel gates.
- [x] Public documentation, changelog, and `0.5.0` release notes.
