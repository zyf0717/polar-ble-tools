# SPEC-005: Protected compatibility and release evidence

**Status:** Deferred
**Depends on:** SPEC-003 core BLE tooling; SPEC-004 where decoder evidence is claimed

See the [deferred tracker](tracker.md).

## Scope

This specification owns protected hardware, fixture, privacy, and release
evidence deferred from SPEC-003:

- Loop Gen 2 and Verity Sense capability matrices;
- two-physical-device concurrency and cancellation validation;
- reconnect and controlled radio-loss testing;
- protected REC/BPB fixture evidence;
- private-data retention and evidence-redaction policy;
- restricted-artifact audits and release-candidate certification.

The normative source requirements are SPEC-003 FR-040 through FR-045, FR-058,
FR-064, and FR-065 as originally proposed. Existing controlled observations may
seed the test plan but do not complete this specification.

## Boundaries

- Unit tests are not hardware compatibility evidence.
- Public documentation claims only redacted behaviors exercised on controlled
  hardware or fixtures.
- Real device data, identifiers, profiles, decoded payloads, and secrets remain
  private and are never committed or uploaded.

## Completion

SPEC-005 requires an explicit private test matrix, evidence schema, retention
policy, and release approval record.
