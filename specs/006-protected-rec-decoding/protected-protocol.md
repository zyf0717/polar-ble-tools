# Protected REC sidecar protocol

This is a deferred protocol contract. It is not a current CLI or Python API.

## Negotiation

Protocol v1 remains the unencrypted protocol owned by SPEC-004. Protocol v2 is
required for secret-bearing operations.

The Python caller chooses a protocol only after a verified `version` handshake:

- an unencrypted single-file decode may use v1 or v2;
- a protected decode requires v2;
- a v1 sidecar receiving a protected request is reported as
  `recording_security_unsupported`;
- version mismatch never falls back after a request has been sent.

Protocol-v2 handshakes expose a sorted `protocol_versions` array and
`capabilities` identifying protected-decode strategies. Capability absence is
unsupported, not evidence of support.

## Request

The sidecar is started with:

```text
<decoder> request --protocol 2
```

Input path, output path, and secret are not placed in argv. Python writes one
UTF-8 JSON request followed by a newline, closes stdin, and reads bounded
stdout/stderr concurrently.

```json
{
  "protocol_version": 2,
  "request_id": "opaque-random-id",
  "operation": "decode",
  "source": {
    "path": "/resolved/input.REC",
    "sha256": "64 lowercase hexadecimal characters"
  },
  "destination": {
    "path": "/private/staging/output.jsonl"
  },
  "secret": {
    "strategy": "vendor-validated-project-value",
    "encoding": "base64",
    "key": "base64 bytes"
  }
}
```

`secret` is omitted for unprotected input. Unknown fields, unsupported
operations, invalid digests, malformed base64, duplicate JSON keys, invalid
UTF-8, and over-limit requests are protocol errors. Strategy and key length are
validated by Python before process start and by the sidecar before SDK
invocation.

The request remains in memory and is never written to a manifest, temporary
request file, exception, representation, or diagnostic.

## Secret sources

CLI sources are mutually exclusive:

```text
--secret-file PATH
--secret-stdin
```

Secret bytes are never accepted directly as an option value. A secret file is a
regular, non-symlink, owner-private file on POSIX. Reading stdin completes
before the sidecar starts.

Python accepts an immutable redacted secret model or provider:

```python
SecretProvider = Callable[[RecordingIdentity], RecordingSecret | None]
```

Representations, serialization, equality diagnostics, provider failures, and
exceptions never expose key bytes. The provider is called at most once per
source. Managed runtimes do not claim secure memory erasure.

## Process and diagnostics

The sidecar uses an argument array, `shell=False`, a minimal explicit
environment, bounded concurrent stdout/stderr drains, and a positive timeout.
Timeout or cancellation terminates the complete process group and publishes no
output.

All status, warning, diagnostic, exception, and future batch-summary surfaces
pass through a redaction guard. Stable sidecar codes include:

```text
usage
protocol_incompatible
unsupported_recording
secret_required
secret_invalid
secret_strategy_unsupported
recording_security_unsupported
decode_failed
timeout
sdk_output_contract_mismatch
```

Unknown codes are protocol errors. Stderr is diagnostic only and never
authoritative.

## Official SDK boundary

The JVM sidecar constructs the pinned SDK's security model and calls the pinned
official REC parser. A strategy is enabled only after SDK inspection and
protected fixture evidence prove it. No project-authored parser, decompressor,
decryptor, SDK patch, translated implementation, or Python fallback is allowed.

Successful output reuses the validated JSONL and constrained-publication
contract from SPEC-004, with `protocol_version: 2`.
