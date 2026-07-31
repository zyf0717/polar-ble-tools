# Implementation plan

Work remains deferred until SPEC-004 adapters are certified and batch decoding
is approved as a product priority.

1. Implement strict manifest parsing and deterministic tree discovery.
2. Preflight every source, destination, output parent, and summary.
3. Delegate decoding to the SPEC-004 single-file API.
4. Add immutable per-file outcomes and atomic schema-versioned summaries.
5. Add thin CLI and Python API wrappers.
6. Integrate SPEC-006 providers only after protected decoding is available.
7. Validate every claimed category against the approved corpus.
