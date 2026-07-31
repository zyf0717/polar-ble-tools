# Models and errors

## Schema lifecycle

`SchemaStatus` records the independent active schema commit, installed schema
commits, manifest format, source independence, and an unavailable reason.
Activation accepts an exact full SDK commit and atomically publishes an
owner-private pointer only after verification.

## Decode results

Each result records:

- raw local and device paths, byte size, and SHA-256;
- decoded, unsupported, or failed status and stable failure code;
- schema identifier and protobuf message type;
- schema commit, schema-manifest version, and descriptor SHA-256;
- schema-faithful decoded data;
- derived logical date and its authoritative source, when applicable;
- decoded output path and SHA-256, when published.

Manifest results preserve input ordering and expose aggregate status counts.

## Failure codes

Stable codes include:

```text
schema_unavailable
unsafe_input
input_too_large
source_evidence_mismatch
protobuf_parse_failed
protobuf_uninitialized
logical_date_mismatch
unsafe_output
output_write_failed
manifest_invalid
```

Diagnostic text is not an automation contract. Unknown paths use
`unsupported`, not a failure code.
