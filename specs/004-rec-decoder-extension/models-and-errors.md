# Models and errors

## Models

The current `DecoderStatus` records availability, verification, SDK commit,
protocol version, verification level, and an unavailable reason.

Single-file results record source/destination paths and digests, SDK and decoder
provenance, record counts/types, and ordered project-owned warnings.

## Errors

Required categories include:

```text
RecDecodeError
├── DecoderUnavailableError
├── DecoderManifestError
├── DecoderVerificationError
├── DecoderProtocolError
├── DecoderTimeoutError
├── UnsupportedRecordingError
└── RecordingDecodeError
```

Python exposes project-owned exception classes and the sidecar emits
project-owned status codes. Bounded stderr remains diagnostic text, not a stable
automation contract. Protected secret models/errors moved to SPEC-006; batch
models moved to SPEC-007.
