# Functional requirements

**FR-027** — Add a compatible request-on-stdin protocol for optional recording
security material. The sidecar emits only project-owned JSONL output and never
echoes or persists secrets.

**FR-028** — Secrets are accepted only through mutually exclusive owner-private
file or stdin sources. They never appear in positional arguments, option
values, environment variables, filenames, manifests, reports, or diagnostics.

**FR-029** — Secret requests use validated project-owned encoding and immutable,
redacted models. Length and strategy validation occurs before subprocess
execution.

**FR-030** — Support only security strategies proven by the pinned SDK and
private fixtures. Unknown strategies return typed unsupported results.

**FR-031** — Preserve unprotected protocol-v1 behavior. Negotiate protocol-v2
capability before transmitting any secret.

**FR-032** — Stable security error codes distinguish:

```text
secret_required
secret_invalid
secret_strategy_unsupported
recording_security_unsupported
```

No message contains secret material.

**FR-062** — Protected REC decoding constructs the SDK security model inside
the JVM sidecar and invokes only the pinned official parser. No project-authored
REC metadata parser, payload parser, decompressor, decryptor, SDK patch, or
Python fallback is permitted.
