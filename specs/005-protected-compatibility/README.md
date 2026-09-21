# SPEC-005: Protected compatibility and release evidence

**Status:** Deferred; policy ownership, reviewers, and retention defaults await
maintainer or organizational approval. Consumes SPEC-009 platform gates and
applicable documented device/decoder contracts.

Existing opt-in live probes, capability-scoped compatibility observations, and
repository/history audits are foundations, not a completed certification matrix.
All requirements below remain open. Historical observations in
[compatibility](../../docs/compatibility.md) are inputs, not formal exact-commit
certification under the deferred evidence schema.

SPEC-009 owns macOS/Windows implementation, native CI, and reproducible harnesses.
This spec owns controlled physical evidence, private handling, and support-claim
approval. Decoder implementation does not depend on this certification program.

## Requirements and acceptance

| IDs | Required evidence |
| --- | --- |
| FR-040 | Capability matrix for Loop Gen 2 and Verity Sense, scoped by host/device/version. |
| FR-041 | Loop discovery, platform-appropriate preparation/authentication, connect/disconnect/reconnect, PMD capabilities/settings/status/start/stop/triggers, disk space, raw list/fetch/collect/cleanup dry-run, passive list/collect/cleanup dry-run, one separately approved destructive cleanup, and every claimed schema/decoder category. Pairing/trust flags are host-specific observations, not portable outcomes. |
| FR-042 | Verity recording capabilities/settings/status/start/stop/triggers, raw retrieval and guarded deletion, and each claimed measurement category. No passive activity/sleep/wellness claim without separate advertisement and validation. |
| FR-043 | Two physical devices demonstrate same-device serialization, bounded independent concurrency, deterministic results, and lock/limiter/notification/session release after cancellation or failure. |
| FR-044 | Controlled reconnect and radio loss establish actual recovery limits without weakened timeouts or unsafe automatic retries. |
| FR-045, FR-091 | Claims bind controlled hardware/fixture evidence to the exact package commit/version. For macOS/Windows, first pass the applicable SPEC-009 implementation gates, then review the physical matrix. Hosted CI, mocks, preliminary observations, and skipped tests do not certify support. |
| FR-058 | Review touched module ownership, duplication, dependency direction, public/internal surfaces, errors/models, test coupling, and documentation drift. |
| FR-064 | Audit repository/history, workflows, wheel/sdist, public artifacts/caches, container layers, build scans, test/coverage/crash reports, SBOM/provenance bundles, temporary archives, LFS, release candidates, and assets for SDK/private material. Project-authored decoder templates are allowed; SDK source/generated artifacts/runtimes, recordings, inventories, profiles, acceptance records, and secrets are not. |
| FR-065 | Fixtures are consented, disposable or approved, synthetic where possible, purpose-limited, access-controlled, and covered by retention/deletion policy. Redact identities, profiles, payloads, secrets, and private paths; retain privacy responsibility and non-medical positioning. |

For claimed decoder/schema categories, bind source/output digests to an
intentional contract version and validate fields, units, nullability, numeric
and timestamp policy. Unknown SDK properties cannot opportunistically become
public fields. Use [REC](../../docs/rec-decoding.md),
[BPB](../../docs/bpb-decoding.md), and pending SPEC-004/006 contracts; claims
remain bounded by [compatibility](../../docs/compatibility.md).

## Evidence contract

The private matrix, roles, consent/access/encryption/retention/deletion defaults,
and public schema require approval before resumption. Proposed public rows contain
only date, package commit/version, device family, host OS/architecture, capability,
`pass|fail|unsupported|unvalidated`, and approved limitation. Exclude device and
participant identifiers, profiles, payloads, secrets, private paths, and raw logs.

- `pass` requires a controlled exercise on the identified commit.
- `unsupported` requires controlled rejection or absence of the capability;
  absent recordings alone do not establish unsupported device functionality.
- `unvalidated` means insufficient controlled evidence; skipped is never pass.
- Passive coverage does not establish waveform or continuous-signal coverage.
- Blocked-only cleanup validates the guard, not eligible cleanup dry-run.

Private records bind each row to fixtures/hardware, procedure, expected outcome,
reviewer, and retention deadline. Keep them outside repository/public automation.

## Resumption and completion

Approve policy and matrix → run both device families and applicable host rows →
exercise concurrency/radio loss and fixtures → audit → rerun exact-release-commit
hardware smoke → review redacted claims → certify and delete expired evidence.
Apply the shared [release gates](../README.md#shared-gates). Detailed external
artifact and release-candidate audit procedures remain deferred.

Stop or mark the capability unvalidated when evidence/consent is absent,
private handling cannot be established, deletion cannot be bounded/audited,
recovery needs unsafe retries, or public infrastructure cannot exclude restricted
material. Existing observations do not bypass these prerequisites.
