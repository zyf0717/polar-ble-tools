# SPEC-008: Official-schema BPB decoding

**Status:** Implemented
**Priority:** Completed ahead of optional REC adapters and orchestration conveniences
**Depends on:** SPEC-003 core BLE tooling

## Scope

SPEC-008 owns passive BPB decoding with locally generated official SDK
protobuf bindings:

- source-independent activation and verification of generated schema caches;
- schema-faithful JSON decoding for every registered BPB schema;
- safe single-file, collection-manifest, and passive-manifest APIs;
- optional post-collection decoding without coupling raw retrieval to the SDK;
- narrowly derived logical-date metadata used by guarded cleanup.

The Python protobuf runtime performs BPB decoding. No JVM sidecar is involved.
The official SDK remains the source of schemas, generated locally through the
existing explicit SDK tooling.

## Documents

- [Requirements](requirements.md)
- [Implementation plan](implementation-plan.md)
- [Models and errors](models-and-errors.md)
- [Validation](validation.md)
- [Governance](governance.md)
- [Tracker](tracker.md)

## Boundaries

- Raw passive retrieval remains usable without SDK source, schemas, or decoder.
- Generated schemas, descriptors, SDK source, BPB inputs, and decoded payloads
  remain local and excluded from distributions and Git.
- Schema activation is independent from SDK-source and REC-decoder activation.
- Output preserves protobuf field names and enum names; derived metadata is
  separate and cannot redefine the decoded payload.
- Compatibility claims require reproducible schema contracts and scoped
  private-fixture evidence.
