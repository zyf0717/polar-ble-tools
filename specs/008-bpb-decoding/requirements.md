# Functional requirements

**FR-067** — Generate BPB Python bindings only from a separately obtained
official SDK checkout using the existing local schema toolchain.

**FR-068** — Record schema-cache format, SDK source repository/ref/commit and
content digest, descriptor digest, generated-file digests, required features,
resolved symbols, dependency closure, and toolchain versions.

**FR-069** — Activate and verify format-3 schema caches independently of the
SDK source checkout. Keep format-2 caches usable only while their matching
verified SDK source remains installed.

**FR-070** — Permit explicit SDK-source removal while retaining generated
schemas. SDK-source, schema, and REC-decoder active pointers remain independent.

**FR-071** — Decode every registered BPB schema to schema-faithful JSON using
generated Python protobuf bindings. Unknown device paths are unsupported, not
guessed.

**FR-072** — Constrain inputs and outputs to configured roots; reject symlinks,
non-regular files, oversized inputs, unsafe output aliases, manifest
size/digest mismatches, and incomplete protobuf messages. Publish owner-private
JSON atomically.

**FR-073** — Expose reusable single-file, collection-manifest, and
passive-manifest decoding APIs and matching CLI commands with stable result
statuses and failure codes.

**FR-074** — Add opt-in `passive collect --decode`. Complete and persist raw
collection first, then decode only the persisted local manifest. Raw collection
must remain successful and inspectable when decoding is unavailable or fails.

**FR-075** — Persist additive passive-manifest decode provenance and only
cleanup-relevant logical dates derived from authoritative payload fields.
Reject payload/path date disagreement instead of silently enriching metadata.

**FR-076** — Preserve raw size and SHA-256 evidence when adding decode
enrichment. Decoded paths are root-relative and decoded files have independent
SHA-256 evidence.

**FR-077** — Prove parse/serialize contracts for every registered official
schema. Scope compatibility statements to the schema revisions and private BPB
fixtures actually exercised.
