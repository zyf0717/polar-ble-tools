# SPEC-005: Protected compatibility and release evidence

**Status:** Deferred; policy ownership and protected validation pending
**Depends on:** SPEC-003

## Scope

SPEC-005 owns evidence that cannot be established by public unit tests:

- Loop Gen 2 and Verity Sense hardware capability matrices;
- two-device concurrency, cancellation, reconnect, and radio-loss exercises;
- protected REC/BPB fixture contracts;
- private-data retention, consent, deletion, and evidence redaction;
- restricted-artifact audits and exact-commit release certification.
- deferred macOS and Windows host workflows and physical-device certification.

Existing controlled observations inform the program but complete only the
specific rows they exercised.

## Implemented foundations

- opt-in live probes cover selected reconnect/PMD, passive retrieval and decode,
  cleanup dry-run, and optional two-device read-only concurrency behavior;
- public compatibility documentation records capability-scoped observations
  and limitations;
- the release audit scans tracked paths, Git history, secret signatures, and
  leaked local paths.

These foundations are not a completed evidence matrix, approved governance
policy, or exact-commit release certification.

Decoder claims consume the applicable SPEC-004 or SPEC-006 validation result;
they do not make those implementation specifications depend on SPEC-005.

## Documents

- [Requirements](requirements.md)
- [Evidence contract](evidence-contract.md)
- [Implementation plan](implementation-plan.md)
- [Validation](validation.md)
- [Governance](governance.md)
- [Tracker](tracker.md)

## Boundaries

- Unit tests are not hardware compatibility evidence.
- Public claims contain only approved redacted evidence.
- Device data, identifiers, profiles, decoded payloads, and secrets remain
  private and never enter Git or public artifacts.
- Absence of evidence is documented as unsupported or unvalidated.
