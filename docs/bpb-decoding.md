# BPB decoding

Decode supported local BPB files with a verified active schema cache generated
from the official SDK. [SDK integration](sdk-integration.md) owns installation,
provenance, verification, and independent activation. Python protobuf bindings
perform decoding; no JVM REC sidecar is involved. Unknown device paths are
`unsupported`, never guessed or mapped from an isolated nested message.

## Entry points

| CLI | Python (`polar_ble_tools.bpb_decode`) |
| --- | --- |
| `polar-ble bpb decode` | `decode_bpb_file()` |
| `polar-ble bpb decode-manifest` | `decode_bpb_manifest()` |
| `polar-ble bpb decode-passive-manifest` | `decode_passive_manifest()` |

`passive collect --decode` first finishes raw collection and manifest publication,
then decodes persisted local evidence. Raw retrieval remains usable and its
results inspectable when schemas are unavailable or decoding fails. See
[passive persistence](passive-files.md#persistence-and-existing-file-policy).

## Results and safety

Output preserves protobuf field and enum names. Derived metadata is separate
from schema-faithful decoded data and cannot redefine payload semantics.
Each result records raw local/device paths, byte size and SHA-256, status,
stable failure code, schema identifier/message type, schema commit/manifest
version/descriptor digest, decoded data, authoritative logical date when
available, and published output path/digest. Manifest results preserve input
order and report aggregate status counts.

Reads are bounded and reject symlinks, non-regular or oversized inputs,
root escapes, source-evidence size/digest mismatches, and incomplete protobuf
messages. Output rejects unsafe aliases and is owner-private and atomically
published within its configured root.

Passive manifest v2 adds decode provenance without changing raw size/hash
evidence. Decoded paths are root-relative and carry their own SHA-256. Read
compatibility with v1 is retained. Cleanup-relevant dates may come only from
known authoritative payload fields; payload/path disagreement fails decoding.
Unknown dates remain ineligible for deletion; decoded output never replaces
raw deletion evidence.

## Status and failure codes

Statuses are `decoded`, `unsupported`, and `failed`. Automation uses codes;
diagnostic text is not a stable interface.

```text
schema_unavailable       unsafe_input             input_too_large
source_evidence_mismatch protobuf_parse_failed    protobuf_uninitialized
logical_date_mismatch   unsafe_output            output_write_failed
manifest_invalid
```

An unknown path is unsupported, not a failure code. Local official-binding
round trips prove schema wiring; device support still depends on the scoped
fixtures in [compatibility](compatibility.md). Licensed fixture configuration
is documented in [SDK integration](sdk-integration.md).
