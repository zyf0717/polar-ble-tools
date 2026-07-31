# Raw and passive operation contracts

This document makes the operational details of FR-001 through FR-020
normative. The base package remains sufficient for every operation described
here; schema-backed BPB decoding is optional and separate.

## Common device workflow

All validation that depends only on caller input must complete before acquiring
a device lock or opening a BLE session. Once validation succeeds, one
`DeviceWorkflowRunner` invocation owns connection, protocol clients, and
disconnect for the complete operation.

Device operations have the following failure behavior:

- input, selection, path, and setting errors open no BLE session;
- protocol errors scoped to one listed or fetched file become per-file results
  when the operation can safely continue;
- connection loss, adapter failure, cancellation, or another transport failure
  aborts the workflow;
- context exit attempts notification shutdown and disconnect after success,
  failure, or cancellation;
- cleanup failure must not replace the original exception, but must remain
  observable through exception chaining or structured diagnostics.

## Recording types and settings

Public recording-control functions accept canonical project-owned measurement
types or their documented aliases. Canonical serialized values are uppercase:

```text
ACC
GYRO
MAGNETOMETER
PPG
PPI
HR
SKIN_TEMPERATURE
```

Additional types may be exposed only when the device reports them and the
project has a project-owned mapping. SDK or PMD enum names must not leak into
serialized output.

CLI settings use repeatable `KEY=VALUE` arguments. Keys normalize by trimming,
uppercasing, and replacing `-` with `_`; values are integers accepted by
Python's base-zero syntax. Empty keys, unknown keys, duplicate keys, negative
values where the PMD field is unsigned, and values wider than the owning PMD
field are validation errors.

`recording_settings(..., full=False)` queries settings available in the current
device mode. `full=True` queries the full offline setting set and may require
SDK mode on supported devices. HR and PPI setting queries return a typed
unsupported error unless device evidence establishes a settings contract for
them.

Starting without settings sends an empty selected-setting set. Starting with
settings validates every key/value against the selected measurement type before
the session opens where local metadata permits; device-reported incompatibility
remains a protocol error. A successful start result means the PMD start command
was acknowledged, not that a file has already been persisted.

Stopping sends one stop command and waits for that measurement to leave both
offline-active states using the existing bounded poll. Timeout is a typed
timeout error; the operation must not report success from command
acknowledgement alone.

## Trigger contract

Canonical trigger modes are:

```text
disabled
system-start
exercise-start
```

`disabled` requires an empty measurement selection. Other modes require at
least one measurement type. CLI settings on `trigger set` apply to every
selected type and must be valid for each; callers needing distinct settings use
the Python API's per-type mapping.

PPI with `exercise-start` is rejected before connection. Disabled or
device-unsupported trigger entries returned by PMD are omitted from the enabled
feature map. A trigger update result contains the requested normalized mode,
the enabled types, and `updated: true`; it must not imply that a recording has
started.

## Targeted raw fetch

The only accepted device path grammar is:

```text
/U/<user-index>/<YYYYMMDD>/R/<HHMMSS>/<record-name>.REC
```

Rules:

- the path is absolute POSIX syntax with no empty interior segment, `.` or
  `..`;
- `<user-index>` is a non-negative decimal integer;
- date and time segments are calendar-valid;
- the filename is one regular filename ending in `.REC`, case-insensitively;
- no wildcard, directory fetch, family expansion, or parent cleanup is
  permitted;
- the normalized path sent to PFTP is the exact validated path.

The local output is resolved without following a pre-existing output symlink.
Source/output alias checks run before connection. Existing output is rejected
unless the public API and CLI expose an explicit overwrite option; overwrite
never applies to the source recording.

Bytes are streamed or buffered under an explicit size bound, hashed with
SHA-256, written to a temporary regular file in the destination directory,
flushed, and atomically published. A failed fetch or publication leaves no
partial final file. The result contains:

```text
device_id
device_path
output_path
fetched_size
sha256
observed_at
```

If the directory listing supplied an expected size, a mismatch is a storage
verification error and the output is not published.

## Disk-space result

Disk-space output uses bytes and the underlying fragment counters:

```text
fragment_size
total_fragments
free_fragments
total_bytes
free_bytes
used_bytes
```

All values are non-negative integers. `total_bytes` and `free_bytes` are
derived from fragment counts, and `used_bytes = total_bytes - free_bytes`.
Missing fields, negative derived space, or overflow beyond the project-owned
integer bound is a protocol error.

## Passive domains and paths

Canonical passive domains and known path families are:

| Domain | Device path |
| --- | --- |
| `activity_samples` | `/U/0/YYYYMMDD/ACT/*.BPB` |
| `daily_summary` | `/U/0/YYYYMMDD/DSUM/DSUM.BPB` |
| `autos` | `/U/0/AUTOS/AUTOSnnn.BPB` |
| `sleep` | `/U/0/YYYYMMDD/SLEEP/SLEEPRES.BPB` |
| `sleep` optional companion | `/U/0/YYYYMMDD/NSTRESUL/NSTRCONT.BPB` |
| `nightly_recharge` | `/U/0/YYYYMMDD/NR/NR.BPB` |
| `skin_temperature` | `/U/0/YYYYMMDD/SKINTEMP/TEMPCONT.BPB` |

Only exact files matching a selected canonical domain are collected or
deleted. A directory not found response and an absent optional file are normal
`missing` outcomes. Other PFTP response errors remain protocol failures.

The path date is the logical date for date-scoped domains. `autos` logical
dates may be derived only from a successfully decoded project-owned payload
contract; otherwise they remain unknown. Unknown dates may be collected but
are never eligible for deletion.

Passive data is low-rate context or an algorithm output. It must not be
described as equivalent to raw ACC, PPG, PPI, or other PMD waveform data.

## Passive sync lifecycle

A mutating or device-reading passive operation uses exactly one complete sync
session:

```text
request synchronization
→ initialize session
→ start sync
→ list/fetch/remove exact files
→ stop sync(completed=<true only on success>)
→ terminate session
```

The project-owned PFTP implementation may combine protocol messages where the
device contract requires it, but the observable ordering and completion flag
remain as above. Teardown is attempted in `finally`. If the body fails,
`completed` is false. If teardown also fails, the body failure remains primary.

A cleanup dry run is a local manifest-verification operation. It opens no BLE
session and sends no sync or remove message.

## Passive persistence and existing-file policy

The existing-file policy is explicit:

```text
skip       default; reuse only an exactly reverified local artifact
overwrite  refetch and atomically replace the local artifact
```

`skip` preserves the pre-`0.3.0` behavior. A local file is skipped only when
the latest applicable manifest row and the current device listing agree on
device identity, domain, exact device path, and size, and the local size and
SHA-256 still verify. Otherwise it is fetched.

`overwrite` refetches even when a verified row exists, atomically replaces the
local raw BPB file, and appends a new manifest row. Historical rows remain
unchanged. The latest valid row for an exact device path is authoritative.

Manifest rows are schema-versioned, append-only JSONL and contain:

```text
schema_version
device_id
domain
logical_date
device_path
local_path
device_size
fetched_size
sha256
fetched_at
status
```

`local_path` is store-relative and must resolve inside the configured passive
root. Device-path components must not escape that root. Manifest parsing fails
closed on a malformed completed row. A final torn row from an interrupted
append may be ignored only when it lacks a newline terminator; it must never
become deletion evidence.

Raw BPB persistence completes before a manifest row is appended. Failure to
append the manifest leaves the source device file untouched and the local file
ineligible for cleanup. Optional decoded output never replaces the raw BPB as
the authoritative deletion evidence.

## Passive deletion selection

`delete-after-collect` considers only `fetched` and exactly reverified
`skipped` rows from the current successful sync. It then:

1. discards entries with unknown logical date;
2. finds the latest logical date observed among eligible rows;
3. retains every entry on that latest date;
4. reverifies remaining entries immediately before removal;
5. removes only each exact BPB file, never a date or domain directory.

If no eligible dated row exists, nothing is deleted and no deletion audit row
is emitted.

Standalone cleanup selects the latest manifest row per exact device path,
restricted to one canonical domain and `logical_date <= delete_through`.
`delete_through` must be earlier than the host's current local date. The
selection is deterministically ordered by logical date and device path and is
reverified immediately before each attempted remove.

Every selected path produces one append-only audit row, including dry-run and
blocked results. Audit rows include the FR-018 fields plus `schema_version` and
an operation identifier shared by the enclosing run. A dry run records
`dry_run`; an unverified row records `blocked_unverified`; neither sends
PFTP `REMOVE`.

Deletion is idempotent only at the result-model level: a subsequent run may
report that the device path is absent, but must not rewrite an earlier audit
row or claim a second successful removal.
