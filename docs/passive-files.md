# Passive BPB retrieval and cleanup

Passive list/collect/cleanup works without SDK schemas or a REC decoder.
Select explicit domains and inclusive date ranges through the
[CLI or Python APIs](cli-reference.md). Optional
[BPB decoding](bpb-decoding.md) runs after raw persistence.

## Domains and paths

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

## Sync lifecycle

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

## Persistence and existing-file policy

The existing-file policy is explicit:

```text
skip       default; reuse only an exactly reverified local artifact
overwrite  refetch and atomically replace the local artifact
```

A local file is skipped only when
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

## Deletion selection

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
blocked results. Audit rows contain schema version, shared operation identity,
device/domain/date/path, local size/digest verification, status, deleted paths, error, and
dry-run state; they contain no payload. Statuses are `deleted`, `dry_run`,
`blocked_unverified`, `blocked_date`, `blocked_domain`, and `failed`. A dry run
records `dry_run`; an unverified row records `blocked_unverified`; neither sends
PFTP `REMOVE`.

Deletion is idempotent only at the result-model level: a subsequent run may
report that the device path is absent, but must not rewrite an earlier audit
row or claim a second successful removal.

Cleanup rejects aggregate domains, current/future cutoffs, unknown dates, and
paths outside the selected domain. Logical dates are device-local calendar
dates; audit timestamps are UTC. Listings and results are deterministically
ordered. A transport failure after a remove attempt is audited before it is
re-raised; a failed fetch, manifest append, or verification leaves the source
untouched. See [workflow failure semantics](architecture.md#workflow-failures).
