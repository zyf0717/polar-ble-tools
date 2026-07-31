# Validation

## Public synthetic tests

- format-3 generation provenance and source-independent verification;
- legacy format-2 source-bound verification;
- independent source/schema activation and retained-schema source removal;
- corrupt pointer, manifest, descriptor, generated file, and toolchain rejection;
- all registered path-to-message mappings;
- protobuf parse, required-field, enum-name, and field-name preservation;
- symlink, non-regular, oversized, traversal, alias, and digest rejection;
- atomic owner-private output publication;
- collection-manifest and passive-manifest ordering and status aggregation;
- post-collection decode isolation and combined CLI exit semantics;
- AUTOS logical-date enrichment and payload/path disagreement rejection;
- passive-manifest v1 reading and v2 decode-evidence round trips.

## Licensed local contracts

- regenerate bindings from the configured official SDK checkout;
- parse and serialize a minimal valid message for every registered schema;
- decode each configured private BPB fixture and validate only its scoped
  schema/path/date contract;
- retain no SDK source, generated binding, descriptor, fixture, or decoded
  payload in Git, distributions, CI artifacts, or logs.

A skipped licensed or private contract is not passing evidence.
