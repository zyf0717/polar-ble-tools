# SPEC-007: REC batch decoding

**Status:** Deferred until SPEC-004 adapters are certified and batch decoding
is approved as a product priority. Protected inputs also require SPEC-006.

**FR-033, FR-034:** add `rec decode-tree` / `rec decode-manifest` and corresponding
`decode_recording_tree()` / `decode_recording_manifest()` APIs.
[The pending protocol](batch-protocol.md) solely defines FR-035–039 discovery,
preflight, per-file outcomes, summaries, and optional providers. Delegate every
decode to the [verified single-file API](../../docs/rec-decoding.md).

Acceptance covers deterministic case-insensitive discovery, strict manifests
(including duplicate keys and final newline), root/symlink/alias/digest safety,
all-destination preflight before any decode, constrained overwrite, continued
per-file execution, atomic summaries, stable exit status, and once-per-source
redacted providers. No source/unrelated-file overwrite or complete-looking
partial summary. Validate claimed categories against the private corpus under
SPEC-005 and apply the shared [gates](../README.md#shared-gates).
