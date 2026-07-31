# Functional requirements

SPEC-003 owns the release-ready BLE recording, retrieval, persistence, and
guarded-cleanup surface. Single-file structured REC decoding is owned by
SPEC-004, protected REC decoding by SPEC-006, and batch REC decoding by
SPEC-007. Protected hardware certification and private evidence are owned by
SPEC-005.

## Recording-control surface

**FR-001** — Provide high-level asynchronous Python APIs for available recording
types, active status, settings, start, stop, offline triggers, disk space, and
targeted raw-file retrieval.

**FR-002** — Export common operational APIs from the documented top-level
facade; keep specialized result and protocol models in their owning modules.

**FR-003** — Provide equivalent `polar-ble raw` CLI operations:

```text
types
status
settings
start
stop
trigger get
trigger set
disk-space
fetch
list
collect
cleanup
```

**FR-004** — Reuse project-owned PMD, PFTP, offline-recording, workflow, and
storage boundaries. Commands do not construct protocol packets or own
persistence policy.

**FR-005** — Normalize and validate measurement types, settings, trigger modes,
duplicate keys, integer bounds, and exact raw paths before device acquisition
where possible.

**FR-006** — `raw stop` waits for bounded inactive status and returns a typed
timeout if the device does not settle.

**FR-007** — Reject unsupported PPI exercise-start triggers.

**FR-008** — Targeted raw fetch validates the exact Polar REC path grammar,
fetches one file, rejects source/output aliasing and unrequested overwrite,
publishes atomically, and returns size and SHA-256 metadata.

**FR-009** — Device-facing public functions serialize by normalized device
identity through `DeviceWorkflowRunner`.

**FR-010** — Machine-facing CLI success output is stable JSON; errors preserve
their subsystem category and use stderr.

## Passive collection and deletion

**FR-011** — Provide passive list, collect, and cleanup CLI operations with
inclusive date ranges, explicit domains, `skip|overwrite` existing-file policy,
guarded delete-after-collect, date-bounded cleanup, and dry-run.

**FR-012** — Provide public asynchronous list, collect, and cleanup APIs.

**FR-013** — Device-facing passive operations own the complete PFTP sync
lifecycle. Teardown runs after success, failure, or cancellation. Local cleanup
dry-run opens no BLE session.

**FR-014** — Passive deletion requires an exact matching manifest row, device
identity, domain, logical date, device path, local file, size, and SHA-256.

**FR-015** — Delete-after-collect considers only successfully fetched or
reverified skipped files. It retains unknown-date records and every file on the
latest eligible logical date.

**FR-016** — Fetch, persistence, manifest, or verification failure leaves the
device source untouched.

**FR-017** — Cleanup rejects aggregate domains, current/future cutoffs,
unknown-date records, and paths outside the selected domain.

**FR-018** — Every passive deletion attempt appends a payload-free JSONL audit
record with operation identity, device/domain/date/path, local verification
metadata, stable status, deleted paths, error, and dry-run state.

**FR-019** — Passive deletion statuses are constrained project-owned values:

```text
deleted
dry_run
blocked_unverified
blocked_date
blocked_domain
failed
```

**FR-020** — Per-file protocol failures produce explicit failed results and
allow safe continuation; transport failures are audited where mutation was
attempted and then abort the workflow.

## Architecture and maintainability

**FR-046** — Responsibilities remain in their owning layers:

```text
commands       argument parsing and process exit behavior
api/collection stable workflow entry points and result composition
device/workflows session ownership, locking, and concurrency
polar          PMD/PFTP/setup protocol behavior
raw_data       REC persistence, verification, and deletion audit
passive_data   BPB persistence, verification, and deletion audit
```

**FR-047** — Repeated device-session orchestration is shared only through typed
workflow helpers used by multiple real operations.

**FR-048** — Raw and passive storage share only identical low-level mechanics,
including atomic publication, streaming digest verification, and JSONL append.
Eligibility, manifests, result models, and audit policy remain domain-specific.

**FR-050** — New and materially changed functions have one orchestration or
validation responsibility and avoid deeply nested control flow.

**FR-051** — Repeated statuses and modes use enums or constrained project-owned
models internally; serialized boundaries retain stable strings.

**FR-052** — Shared atomic publication, SHA-256, JSONL, path, date, and setting
semantics have one implementation where their invariants match.

**FR-053** — Public result collections are immutable or defensively copied.
Frozen dataclasses and tuples are the default.

**FR-054** — Validation, transport, protocol, timeout, unsupported-operation,
and storage failures retain their typed category. Broad translation must not
turn a dead BLE link into a per-file protocol result.

**FR-055** — Public APIs and non-obvious protocol/lifecycle boundaries have
type annotations and concise contract docstrings.

**FR-056** — Tests target public behavior and stable subsystem boundaries rather
than private implementation structure.

**FR-057** — Obsolete in-scope shims, duplicate parsers, unused models, and dead
paths are removed without breaking the documented pre-`0.3.0` CLI contract.
