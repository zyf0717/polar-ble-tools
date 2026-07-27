# Evidence contract

## Identifiers and storage boundaries

- Assign each exercise an opaque `evidence_id` generated independently of the
  device, participant, fixture path, and operator. It is the only join key
  permitted in public rows.
- Store the private matrix and its artifacts in the approved restricted store,
  never in the repository, issue tracker, public CI, or release assets.
- Public rows may be committed only after review against the private row and
  the redaction rules below.

## Private test matrix

The private matrix is schema version `1`. Each row contains exactly these
logical fields:

```text
schema_version
evidence_id
procedure_id and procedure_revision
package_commit and package_version
device_family and private_device_id
host_os and host_architecture
operation
preconditions
expected_outcome
observed_outcome
result
artifact_digests
fixture_ids
operator
reviewer
started_at and completed_at
consent_record
retention_deadline
deletion_status
approved_public_limitation
```

`package_commit` is a full lowercase Git SHA. `result` is one of `pass`,
`fail`, `unsupported`, or `unvalidated`. Artifact references are content
digests plus restricted-store identifiers, never local paths. `operator`,
`reviewer`, `private_device_id`, fixture identifiers, and consent records are
private.

Every claimed operation/device/architecture combination has its own row.
Evidence is not inherited between devices, architectures, measurement
categories, passive domains, protected/unprotected recordings, or package
commits. A rerun creates a new row; it does not overwrite the prior record.

## Redacted public evidence schema

A public row is schema version `1` and contains only:

```text
schema_version
evidence_id
observed_date
package_commit
package_version
device_family
host_os
host_architecture
operation
outcome
approved_limitation
```

`observed_date` is an ISO `YYYY-MM-DD` date. `outcome` is one of `pass`,
`fail`, `unsupported`, or `unvalidated`. Free text is limited to the
project-owned operation name and a reviewed limitation; it must not contain
private paths or copied diagnostics. A public row is rejected if any required
field is absent, any unknown field is present, or the private reviewer has not
approved its exact content.

Public evidence excludes MAC addresses, serial numbers, participant/operator
identifiers, private device or fixture IDs, profile content, raw or decoded
payloads, timestamps more precise than the observed date, secrets, exact
private paths, retention metadata, and unredacted logs.

## Evidence semantics

- `pass` requires a controlled exercise on the identified commit.
- `unsupported` means the protocol/device rejected or did not expose the
  capability under the controlled contract.
- `unvalidated` means no sufficient controlled evidence exists.
- `skipped` is never interpreted as pass.
- Passive time coverage does not prove raw waveform or continuous-signal
  coverage.
- Unit/contract tests prove software behavior, not physical-device support.
- A previous-commit pass is not evidence for a release candidate.
- A capability advertisement is not recording, retrieval, or decoding
  evidence.
- Raw retrieval is not schema or payload-decoding evidence.

## Review and publication

Before publication, the reviewer verifies the procedure revision, exact package
commit/version, expected and observed outcomes, artifact digests, result,
limitation, consent state, and retention deadline. The reviewer then compares
the exact public row with this allowlist. A failed review leaves the capability
`unvalidated`; it is not partially published.
