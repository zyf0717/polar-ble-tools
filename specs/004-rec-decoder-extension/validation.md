# Validation

## Public synthetic tests

- architecture selection and host alias normalization;
- checksum, archive traversal, symlink, and platform mismatch rejection;
- transactional activation and rollback;
- interactive SDK licence confirmation and `-y` prompt bypass;
- protocol-v1 compatibility and protocol-v2 negotiation;
- secret canaries absent from argv, environment, output, errors, logs,
  manifests, summaries, and filenames;
- request/response size, encoding, duplicate-key, timeout, and process-group
  cleanup behavior;
- deterministic tree/manifest discovery and destination preflight;
- strict JSONL header/record/summary validation;
- explicit adapter mappings unaffected by reflection order or new SDK fields.

## Protected local contracts

- build and self-test each claimed architecture;
- prove invocation of the pinned official SDK parser;
- decode every claimed private fixture category;
- validate protected fixtures separately;
- verify source/output digests, counts, types, and adapter contracts;
- upload or retain no SDK source, classes, recordings, decoded data, or secrets.

Protected contracts never run in public CI.
