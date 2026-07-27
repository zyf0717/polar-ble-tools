# SPEC-004 tracker

All items are deferred beyond `0.3.0` and governed by
[requirements.md](requirements.md).

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

## Phase 2 — protected sidecar protocol

- [ ] **FR-027** — Compatible non-argv secret transport.
- [ ] **FR-028** — Private file/stdin secret sources and leakage prevention.
- [ ] **FR-029** — Validated, redacted project-owned secret models.
- [ ] **FR-030** — Evidence-backed secret strategies only.
- [ ] **FR-031** — Protocol negotiation before secret transfer.
- [ ] **FR-032** — Stable redacted security error categories.
- [ ] **FR-062** — Official SDK parser only; no fallback parser/decryptor.

## Phase 3 — batch decoding and adapters (deferred)

Batch CLI/API work is deferred until the single-file decoder is certified
against the protected corpus and the feature is approved as a product priority.

- [ ] **FR-033** — Tree and manifest batch CLI.
- [ ] **FR-034** — Corresponding public Python APIs.
- [ ] **FR-035** — Deterministic, symlink-safe, atomic tree decoding.
- [ ] **FR-036** — Strict schema-versioned manifest validation.
- [ ] **FR-037** — Destination preflight and constrained overwrite.
- [ ] **FR-038** — Versioned batch summaries.
- [ ] **FR-039** — Secure once-per-source secret resolution.
- [x] **FR-049** — Cohesive REC-module decomposition.
- [ ] **FR-063** — Explicit stable payload adapter contracts.
