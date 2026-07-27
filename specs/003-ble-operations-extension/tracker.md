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
- [ ] **FR-050** — Keep new or materially changed functions narrow and shallowly nested.
- [ ] **FR-051** — Replace repeated stringly typed statuses, modes, and errors with constrained project-owned models.
- [ ] **FR-052** — Centralize the specified cross-cutting publication, path, hashing, JSON, redaction, subprocess, date, and setting utilities where semantics are shared.
- [ ] **FR-053** — Prevent public APIs from returning mutable internal collections.
- [ ] **FR-054** — Preserve the typed subsystem error hierarchy without broad information-losing translation.
- [ ] **FR-055** — Add docstrings and annotations to new public APIs and non-obvious internal boundaries.
- [ ] **FR-056** — Test public behavior and stable contracts without excessive implementation-detail mocking.
- [ ] **FR-057** — Remove obsolete in-scope shims, models, parsers, and paths without breaking documented 0.2.x behavior.

## Phase 2 — passive deletion safety and storage refactor

- [ ] **FR-011** — Provide `passive collect` and `passive cleanup` CLI operations and options.
- [ ] **FR-012** — Provide public async collection and cleanup APIs.
- [ ] **FR-013** — Implement the required PFTP sync lifecycle, including failure/cancellation teardown and local-only cleanup dry runs.
- [ ] **FR-014** — Gate deletion on exact manifest, file, size, digest, device, domain, and date verification.
- [x] **FR-015** — Restrict delete-after-collect eligibility and retain unknown/latest logical-date records.
- [ ] **FR-016** — Preserve source device files after fetch, decode, manifest, or verification failure.
- [ ] **FR-017** — Reject unsafe cleanup domains, cutoffs, unknown dates, and out-of-domain files.
- [ ] **FR-018** — Append immutable, secret-free JSONL audit records for every deletion attempt.
- [ ] **FR-019** — Use the specified stable passive-deletion statuses.
- [ ] **FR-020** — Continue across per-file protocol failures while aborting on transport failures.
- [ ] **FR-048** — Share raw/passive storage utilities only where invariants truly match; retain domain-specific models and eligibility.

## Phase 3 — Linux aarch64 sidecar, SDK lifecycle, and toolchain model refactor

- [ ] **FR-021** — Support sidecar build and execution on Linux x86_64 and aarch64.
- [ ] **FR-022** — Pin and verify architecture-specific Temurin metadata; normalize architecture aliases.
- [ ] **FR-023** — Pin Gradle and share safe extraction/verification logic across architectures.
- [ ] **FR-024** — Record required toolchain, runtime, protocol, adapter, and package metadata in decoder manifests.
- [ ] **FR-025** — Report cross-platform/architecture sidecars as unavailable with an actionable rebuild command.
- [ ] **FR-026** — Preserve all archive, executable, digest, cache-boundary, and rollback protections on aarch64.
- [ ] **FR-059** — Generate SDK schemas/bindings locally from licensed inputs only; keep generated material cache-only and fail unavailable when absent.
- [ ] **FR-060** — Bind SDK licence acceptance to exact verified staged content without recording personal or public-artifact data.
- [ ] **FR-061** — Include, hash, verify, and confine required decoder-local licence/notices; exclude them from all public distributions and artifacts.

## Phase 4 — secret-aware sidecar protocol and invocation refactor

- [ ] **FR-027** — Add compatible stdin-based, non-argv secret transport and project-owned JSONL protocol output.
- [ ] **FR-028** — Prevent secret transport through argv, unsafe environment variables, filenames, manifests, and reports; support only private file/stdin CLI sources.
- [ ] **FR-029** — Use validated project-owned secret encoding and construction-time redaction.
- [ ] **FR-030** — Support only SDK- and fixture-proven secret strategies; return typed unsupported errors otherwise.
- [ ] **FR-031** — Preserve v1 behavior and negotiate v2 before sending any protected secret material.
- [ ] **FR-032** — Distinguish required secret error categories without exposing secret material.
- [ ] **FR-062** — Decode protected REC only through the pinned SDK parser and project-owned sidecar contracts; never implement a fallback parser/decryptor.

## Phase 5 — batch decoding and REC module decomposition

- [ ] **FR-033** — Provide `rec decode-tree` and `rec decode-manifest` CLI operations.
- [ ] **FR-034** — Provide corresponding public Python APIs.
- [ ] **FR-035** — Implement deterministic, symlink-safe tree decoding, atomic output, per-file continuation, and categorized summary/exit behavior.
- [ ] **FR-036** — Validate schema-versioned manifests and reject unsafe paths, duplicates, unknown fields, and inline secrets before decoding.
- [ ] **FR-037** — Preflight destinations and retain atomic no-clobber semantics; constrain overwrite to validated project-owned outputs.
- [ ] **FR-038** — Produce versioned batch summaries with required environment, counts, hashes, paths, results, codes, and warnings.
- [ ] **FR-039** — Resolve selected secrets through a secure once-per-source provider with redacted identities.
- [ ] **FR-049** — Split modules with unrelated accumulated responsibilities.
- [ ] **FR-063** — Define explicit project-owned adapters and stable payload contracts for each claimed REC category.

## Phase 6 — protected validation, maintenance review, and release readiness

- [ ] **FR-040** — Extend the protected compatibility matrix for Loop Gen 2 and Verity Sense.
- [ ] **FR-041** — Complete and record the required Loop Gen 2 validation coverage.
- [ ] **FR-042** — Complete and record the required Verity Sense validation coverage without unsupported passive claims.
- [ ] **FR-043** — Prove per-device serialization, bounded cross-device concurrency, and failure/cancellation resource release with two physical devices.
- [ ] **FR-044** — Run controlled reconnect/radio-loss tests and record recovery limitations honestly.
- [ ] **FR-045** — Base compatibility evidence only on controlled fixtures or hardware exercises.
- [ ] **FR-058** — Perform and record each phase’s maintainability review; resolve avoidable touched-subsystem leaks.
- [ ] **FR-064** — Keep all restricted SDK-derived and private material out of public CI, artifacts, images, releases, and Git history.
- [ ] **FR-065** — Keep real-device data private/approved/redacted; document retention, privacy responsibilities, and non-medical positioning.
