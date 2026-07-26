# 8. Sidecar command contract

The built executable must support:

```text
polar-rec-decoder version
polar-rec-decoder self-test
polar-rec-decoder decode --input PATH --output PATH --protocol 1
```

Rules:

- stdout contains exactly one final machine-readable JSON status object;
- diagnostics and logs go to stderr;
- decoded content goes only to the requested output path;
- successful commands exit `0`;
- invalid usage exits `2`;
- unsupported input exits `3`;
- internal decode failure exits `4`;
- protocol incompatibility exits `5`;
- output must not be partially presented as successful.

The Python runtime may support either a native launcher or `java -jar`, but the manifest must define the exact argument array.

## 9. Decoder protocol v1

The first output format is UTF-8 JSON Lines.

### 9.1 Header

The first non-empty line must be:

```json
{
  "type": "header",
  "protocol_version": 1,
  "sdk_commit": "<full commit>",
  "decoder_version": "<adapter version>",
  "source_sha256": "<digest>"
}
```

### 9.2 Records

Each decoded record must use a project-owned envelope:

```json
{
  "type": "record",
  "record_type": "<normalized-slug>",
  "timestamp_ns": 1234567890,
  "payload": {}
}
```

Requirements:

- `record_type` is a stable lowercase project-owned slug;
- `timestamp_ns` is an integer UTC Unix timestamp in nanoseconds or `null`;
- `payload` contains only JSON-compatible project-owned keys and values;
- SDK/Kotlin/Swift class names must not be required by callers;
- unknown but valid fields may be preserved inside `payload`;
- non-finite numbers must be encoded as `null` and reported as warnings;
- binary values must be base64 with an explicit encoding field;
- records must preserve source order unless the official decoder defines a stronger ordering;
- output from the same input, decoder build, and protocol version should be deterministic.

Do not promise semantic normalization that the feasibility spike cannot validate. Prefer a generic stable envelope over speculative domain models.

### 9.3 Summary

The final line must be:

```json
{
  "type": "summary",
  "record_count": 0,
  "record_types": {},
  "warnings": []
}
```

The Python runtime must reject:

- missing or duplicate headers;
- an incompatible protocol version;
- malformed JSON;
- records after the summary;
- a missing summary;
- a source digest mismatch;
- a sidecar success response that disagrees with the output summary.

