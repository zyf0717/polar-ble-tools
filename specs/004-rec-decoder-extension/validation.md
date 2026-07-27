# Validation

## Public synthetic tests

- architecture selection and host alias normalization;
- checksum, archive traversal, symlink, and platform mismatch rejection;
- transactional activation and rollback;
- per-invocation SDK licence confirmation, cache-reuse prompting, legacy-state
  removal, and `-y` prompt bypass;
- exact decoder-local SDK licence attribution copy, manifest commit/digest
  binding, explicit non-acceptance labeling, and distribution exclusion;
- non-fatal doctor warning and rebuild remediation for active SDK/decoder
  commit mismatch;
- protocol-v1 handshake and invocation compatibility;
- bounded stdout/stderr, timeout, and process-group cleanup behavior;
- strict JSONL header/record/summary validation;
- source/output alias rejection and constrained overwrite;
- decoder runtime allowlist and digest verification.

## Protected local contracts

- build and self-test each claimed architecture;
- prove invocation of the pinned official SDK parser;
- decode every claimed private fixture category;
- verify source/output digests, counts, types, and adapter contracts;
- upload or retain no SDK source, classes, recordings, or decoded data.

Protected contracts never run in public CI.

Protected protocol validation moved to SPEC-006. Batch validation moved to
SPEC-007.
