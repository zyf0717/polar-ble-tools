# SPEC-005: Protected compatibility and release evidence

**Status:** Deferred; policy ownership and protected validation pending
**Depends on:** SPEC-003; SPEC-004 where decoder claims are evaluated

## Scope

SPEC-005 owns evidence that cannot be established by public unit tests:

- Loop Gen 2 and Verity Sense hardware capability matrices;
- two-device concurrency, cancellation, reconnect, and radio-loss exercises;
- protected REC/BPB fixture contracts;
- private-data retention, consent, deletion, and evidence redaction;
- restricted-artifact audits and exact-commit release certification.

Existing controlled observations inform the program but complete only the
specific rows they exercised.

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
