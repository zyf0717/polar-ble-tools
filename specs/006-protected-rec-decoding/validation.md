# Validation

## Public synthetic gates

- protocol-v1 preservation and protocol-v2 negotiation;
- secret source mutual exclusion, permissions, encoding, and size validation;
- secret canaries absent from argv, environment, output, errors, logs,
  manifests, summaries, filenames, and representations;
- duplicate-key, invalid UTF-8, malformed request/status, and byte limits;
- timeout and cancellation process-group cleanup;
- stable unsupported/security error codes.

## Protected local gates

- prove invocation of the pinned official SDK parser and security model;
- validate each enabled strategy against approved protected fixtures;
- verify source/output digests and decoded adapter contracts;
- retain or upload no SDK source, recordings, decoded data, or secrets.

Protected gates never run in public CI and follow SPEC-005 governance.
