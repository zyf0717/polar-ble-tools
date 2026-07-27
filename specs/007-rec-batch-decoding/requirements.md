# Functional requirements

**FR-033** — Provide `rec decode-tree` and `rec decode-manifest` CLI operations.

**FR-034** — Provide corresponding `decode_recording_tree()` and
`decode_recording_manifest()` Python APIs.

**FR-035** — Tree decoding selects regular `*.REC` files without following
symlinks, excludes its output subtree, preserves relative paths, orders inputs
deterministically, publishes one validated JSONL output per success, continues
after per-file failures, and writes one summary.

**FR-036** — Manifest decoding accepts only a strict schema-versioned
project-owned format with root-relative paths, optional expected SHA-256, and
opaque provider keys. Reject traversal, absolute paths, symlinks, duplicates,
unknown fields, and inline secrets before decoding.

**FR-037** — Preflight every destination. Default to atomic no-clobber
publication; explicit overwrite may replace only validated project-owned
decoded outputs, never REC sources or unrelated files.

**FR-038** — Batch summaries are versioned and contain deterministic relative
paths, environment/protocol provenance, counts, per-type counts, per-file
results, source/output digests, stable codes, and warnings.

**FR-039** — Resolve selected secrets through a secure provider invoked at most
once per source with only a redacted recording identity.
