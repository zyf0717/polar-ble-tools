# Models and errors

## Models

Decoder status records availability, verification, SDK commit, decoder and
protocol versions, platform, architecture, verification level, capabilities,
reason, and remediation.

Single-file results record source/destination paths and digests, provenance,
record counts/types, and ordered project-owned warnings. Batch results add
schema version, deterministic per-file outcomes, totals, and environment
metadata.

Secret values are immutable byte-oriented models whose representation,
diagnostics, exceptions, and provider identity are redacted by construction.

## Errors

Required categories include:

```text
RecDecodeError
├── DecoderUnavailableError
├── DecoderManifestError
├── DecoderVerificationError
├── DecoderProtocolError
├── DecoderTimeoutError
├── RecordingSecurityError
├── UnsupportedRecordingError
└── RecordingDecodeError
```

Stable errors expose category, code, message, operation, and retryability
without SDK class names, private paths, or secrets. Cancellation terminates the
complete process group and is re-raised.
