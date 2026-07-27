# Models and errors

Batch results add a schema version, deterministic per-file outcomes, totals,
environment/protocol provenance, source/output digests, warnings, and a summary
path to the SPEC-004 single-file result contract.

Per-file status is `decoded`, `unsupported`, or `failed`. Automation uses stable
project-owned error codes; human-readable errors contain no secret, payload, or
private provider data.

Manifest/preflight/publication errors are operation-level failures. Decode
errors are isolated to their selected source and do not prevent later sources
from running.
