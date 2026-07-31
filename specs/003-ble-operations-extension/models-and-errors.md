# Models, errors, and workflow semantics

## Public models

Public operational results are frozen dataclasses. Collection-valued fields are
tuples or defensive copies. Internal raw/passive outcomes use `StrEnum` values;
`to_jsonable()` emits the stable string representation expected by CLI users.

Collection results expose counts consistent with their record outcomes. `ok`
is false for fetch failures, blocked destructive operations, or failed
deletions.

## Error boundaries

The core hierarchy preserves:

```text
validation
BLE transport/connection
PMD protocol/response/timeout/unsupported
PFTP protocol/response/timeout
storage/manifest/verification
```

Per-file protocol or storage errors may become explicit failed records when
continuation is safe. `BleTransportError` and subclasses abort the workflow.
Cancellation propagates as the runtime cancellation sentinel.

## Workflow ownership

`DeviceWorkflowRunner` normalizes identity and acquires:

```text
per-device lock
→ optional global limiter
→ device session
→ operation-specific protocol lifecycle
```

The runner owns connection/session cleanup but no automatic retry policy.
Destructive operations are never retried automatically.

## Time and ordering

Passive logical dates are device-local calendar dates. Audit timestamps are
UTC. Cleanup compares its cutoff to the host current local date. Listings,
manifest selections, and result records are deterministically ordered.

## Deletion semantics

Deletion requires a verified local copy and inactive recording where
applicable. Dry-run performs no device mutation. A transport failure after a
remove attempt records a failed audit outcome before being re-raised.
