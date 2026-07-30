# Functional requirements

SPEC-009 owns BLE lifecycle experimentation, migration decisions, the resulting
`0.5.x` transport/public-contract changes, and portability validation. SPEC-003
continues to own PMD/PFTP operations, retrieval, storage, and guarded cleanup.
SPEC-005 owns physical-platform certification and public support evidence.

## Discovery, identity, and connection

**FR-078** — Maintain a reviewed decision matrix for discovery, target
resolution, preparation, state observation, readiness probing, managed
connection, disconnect, reconnect, cancellation, and recovery. Each row records
the required package outcome, experiment, evidence, verdict, limitations, and
rationale.

**FR-079** — Canonical discovery uses Bleak's structured scanner API and
advertisement data. It returns platform identifiers, display names, RSSI, and
advertised service UUIDs without parsing terminal output or mutating a device.

**FR-080** — The Bleak backend resolves a native `BLEDevice` in the current
async context and passes that object to `BleakClient`. Address or UUID strings
remain selection inputs, not the normal client-construction path. Native
objects are neither public nor persisted across unrelated operations or event
loops.

**FR-081** — Device selection, authorization, inventory loading, locking, CLI
options, models, and diagnostics use a platform-neutral `identifier`. Linux MAC
addresses and macOS UUID identifiers are valid opaque values after
platform-appropriate normalization. Authorization remains explicit before
device mutation.

## Preparation and lifecycle

**FR-082** — Device preparation uses Bleak alone when controlled experiments
show that it enables the package's supported workflows and any required later
reconnect. Exact `bluetoothctl` state flags and command sequencing are not
acceptance criteria.

**FR-083** — The canonical readiness probe owns a bounded connection, verifies
the required Polar PMD/PFTP service surface, reports the result, and
disconnects. Normal commands and Python workflows do not leave an OS-owned
connection for a separate client to release.

**FR-084** — An OS-specific adapter is allowed only when an accepted experiment
proves that Bleak cannot supply a required package outcome. The matrix names
that outcome, affected platforms, adapter API, removal condition, and evidence.
Structured native APIs are preferred over interactive command parsing.

**FR-085** — All device-facing PMD, PFTP, raw, passive, preparation, probe, and
FTU operations acquire the device through shared workflow orchestration. One
component owns each connection, and cleanup runs after success, failure, or
cancellation.

**FR-086** — Discovery, resolution, preparation, connect, service readiness,
disconnect, timeout, cancellation, and backend failures retain typed phase
information. Timeouts are bounded, partial connections are cleaned up, and
diagnostics do not expose inventories, captures, payloads, or unnecessary
device metadata.

## Device-specific FTU

**FR-090** — `apply_ftu()` dispatches a validated device-family profile to one
explicit setup path under the managed Bleak connection. Loop Gen 2 retains its
system/local time, physical-data, user-identifier, and optional settings
workflow. Verity Sense captures current timezone-aware host time after
connection, writes system/local time, and applies wear location through
`UDEVSET.BPB`; it never writes Loop physical data or user identifiers. Verity
runtime time is not profile input, and pool length remains rejected until a
complete generated-schema read/modify/write contract is verified.

## Public contract, evidence, and release

**FR-087** — `0.5.0` replaces MAC-specific and persistent-connection public
contracts with asynchronous, platform-neutral discovery, preparation, bounded
probe, and managed-session contracts. `0.4.x` compatibility aliases and
deprecated ownership paths are not required.

**FR-088** — Automated contracts cover Linux, macOS, and Windows identifier and
lifecycle variants through injected Bleak scanner/client boundaries. Controlled
Linux hardware validation covers both currently supported devices before the
default lifecycle changes.

**FR-089** — Automated cross-platform tests are not physical compatibility
evidence. macOS and Windows 11 remain unvalidated until SPEC-005 records
controlled hardware results. Release documentation distinguishes portable
architecture, tested packaging, and evidence-backed device/platform support.
