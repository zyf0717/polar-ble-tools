# SPEC-003: Core BLE operations

**Status:** Implemented; released in `0.3.0`
**Milestone:** `0.3.0`
**Repository:** `zyf0717/polar-ble-tools`

## Scope

SPEC-003 defines the package’s core Linux/BlueZ BLE tooling:

- offline-recording capability, settings, status, start, stop, and triggers;
- device disk-space inspection and exact raw REC retrieval;
- raw REC listing, verified local persistence, and guarded cleanup;
- passive BPB listing, persistence, delete-after-collect, and cleanup;
- per-device workflow serialization and BLE/PFTP lifecycle ownership;
- immutable public result collections and stable serialized statuses;
- shared atomic publication, JSONL append, and streaming SHA-256 verification.

Single-file structured REC decoding is specified in
[SPEC-004](../004-rec-decoder-extension/README.md), with protected REC and batch
extensions deferred to [SPEC-006](../006-protected-rec-decoding/README.md) and
[SPEC-007](../007-rec-batch-decoding/README.md). Protected hardware, fixture,
privacy, and certification evidence is specified in
[SPEC-005](../005-protected-compatibility/README.md).

## Documents

- [Requirements](requirements.md)
- [Operation contracts](operation-contracts.md)
- [Models and errors](models-and-errors.md)
- [Public contracts](public-contracts.md)
- [Implementation plan](implementation-plan.md)
- [Validation](validation.md)
- [Governance and completion](governance.md)
- [Tracker](tracker.md)

## Boundaries

- BLE, PMD, PFTP, workflow, collection, storage, and verification remain
  project-owned Python.
- Raw and passive retrieval do not require schemas, Java, Gradle, or a decoder.
- Installation and import perform no download, generation, build, activation,
  or device mutation.
- Destructive operations require exact local verification and an audit record.
- Device data and identifiers remain outside Git and public release artifacts.
- Support claims do not exceed `docs/compatibility.md`.
- Higher-level application orchestration remains outside this repository.

## User outcomes

1. An operator can inspect and control supported offline recordings through
   stable CLI or Python APIs.
2. An operator can retrieve one exact REC or collect verified raw recordings.
3. An operator can collect passive BPB files within a complete sync lifecycle.
4. An operator can preview or perform only locally verified device cleanup.
5. An integrator receives immutable results with stable JSON representations
   and typed transport/protocol failure boundaries.
