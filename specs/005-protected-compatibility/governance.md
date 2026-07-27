# Governance

## Roles and authorization

- The fixture owner establishes authority or consent for collection and records
  the permitted purpose, categories, access group, and expiry.
- The operator runs the approved procedure and may access only the fixtures
  needed for that run.
- The reviewer verifies evidence and the exact redacted public row. For a
  destructive device action or a new compatibility claim, the reviewer must
  not be the sole operator.
- The release approver accepts or rejects the exact candidate commit only after
  all required evidence and audits pass.

One person may hold multiple roles except where independent review is required
above. Role names and identities remain private.

## Fixture consent and purpose

Real-device fixtures require a recorded owner or participant authorization
before collection. The record states the approved purpose, data categories,
operations (including whether deletion is allowed), retention deadline, and
withdrawal route. Prefer synthetic fixtures; use disposable recordings for
destructive tests. Do not repurpose fixtures for unrelated development,
analytics, model training, or medical inference.

Consent withdrawal immediately blocks new use. The fixture owner decides
whether an existing public aggregate row must be withdrawn; private material is
deleted unless a documented legal obligation prevents it.

## Access and handling

- Keep inventories, profiles, recordings, decoded outputs, SDK material,
  secrets, logs, and private evidence in an access-controlled restricted store.
- Grant least-privilege, time-bounded access to named roles and review it before
  every certification cycle.
- Do not copy restricted material into Git, Git LFS, public CI, tickets, chat,
  crash reports, build scans, coverage reports, containers, or release bundles.
- Use opaque fixture/device identifiers. Store the identity mapping separately
  with narrower access.
- Encrypt restricted storage and transport using the organization-approved
  controls. Do not place decryption keys beside the fixtures.

## Retention and deletion

Every private fixture and evidence row has an owner and explicit deletion
deadline before use. The default deadline is 30 days after the associated
release is approved or rejected. A longer period requires a documented purpose,
new deadline, and reviewer approval before the current deadline expires.

At expiry or withdrawal, delete source fixtures, derived payloads, logs,
temporary archives, build/report copies, and recoverable trash from every
known location. Retain only the approved redacted public row and a private
deletion receipt containing the opaque evidence ID, categories deleted,
completion time, operator, reviewer, and any verified backup-expiry exception.
The receipt contains no payload, device identity, or private path.

Deletion status is one of `pending`, `complete`, or `blocked`. A blocked
deletion stops certification until the reviewer records and resolves the
exception. Backups that cannot be selectively erased must have a verified
expiry no later than the approved retention deadline.

## Stop conditions

Stop or mark a capability unvalidated when:

- controlled fixture or hardware evidence is absent;
- required evidence would disclose private device or participant data;
- a destructive operation cannot be bounded and audited;
- radio-loss recovery would require unsafe retries or weakened timeouts;
- public infrastructure cannot exclude restricted material;
- fixture consent, access, retention, or deletion cannot be established.

Certification requires reviewed evidence for every public claim, a passing
restricted-artifact audit, exact-commit hardware smoke, approved limitations,
and completion of private retention/deletion actions.
