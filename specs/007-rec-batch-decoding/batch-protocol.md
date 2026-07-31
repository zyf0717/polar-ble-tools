# REC batch protocol

This is a deferred orchestration contract. It is not a current CLI or Python
API.

## Decode-manifest input

The manifest is UTF-8, newline-terminated, project-owned JSONL. Each non-empty
row has:

```json
{
  "schema_version": 1,
  "source": "relative/path/ACC.REC",
  "source_sha256": "optional lowercase SHA-256",
  "secret_id": "optional opaque provider key"
}
```

Rules:

- `source` is relative to the caller-supplied manifest root;
- absolute paths, empty segments, `.`/`..`, symlinks, non-regular files, and
  non-`.REC` suffixes are rejected;
- resolved sources remain inside the manifest root;
- duplicate sources, duplicate destinations, unknown fields, and unsupported
  schema versions fail validation before decoding;
- `source_sha256`, when present, is checked before sidecar invocation;
- `secret_id` is opaque and never contains secret material;
- inline secret fields are forbidden.

A malformed completed row fails before any decode. A final
non-newline-terminated row is malformed, not an ignorable partial entry.

## Tree discovery and output mapping

Tree discovery resolves input and output roots once. It walks without following
directory symlinks, selects readable regular files whose suffix is `.REC`
case-insensitively, excludes the resolved output subtree, and sorts by relative
POSIX path.

For tree and manifest modes:

```text
relative/path/ACC.REC → <output-root>/relative/path/ACC.jsonl
```

Before decoding, preflight verifies source/output aliasing, duplicate
destinations, output-root containment, parent-directory safety, and no-clobber
conflicts. Without overwrite, any existing destination or summary aborts before
the first sidecar invocation.

With overwrite, only regular decoded JSONL destinations that pass SPEC-004
validation may be replaced. Unrelated or stale files are never removed.

## Execution and summary

Every selected source receives one result. Successful sources receive a
validated JSONL output. Unsupported and failed sources receive no placeholder;
their typed outcomes appear in `summary.json`.

The default implementation is sequential. Future bounded concurrency may run
independent sidecars concurrently, but publication, summary ordering, and
provider invocation remain deterministic.

Per-file result:

```text
status              decoded | unsupported | failed
source
relative_path
output
source_sha256
output_sha256
record_type
record_count
record_types
warnings
error_code
error
```

Serialized paths are relative to declared roots unless resolved paths are
explicitly requested. `error` is redacted and human-readable; automation uses
`status` and `error_code`.

`summary.json` is schema-versioned, deterministically ordered, and atomically
published after all selected sources finish. It records environment/protocol
provenance, counts, outcomes, source/output digests, warnings, and normalized
architecture.

Unsupported inputs do not count as failed. CLI exit status is zero when
`failed == 0` and one when any file failed. Preflight or summary-publication
failure is an operation-level failure.

## Protected sources

`secret_id` remains inert unless SPEC-006 is implemented and a provider is
explicitly supplied. The provider receives only a redacted recording identity
and is called at most once per selected source. Provider results and failures
follow SPEC-006 redaction rules.
