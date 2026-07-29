# Experiments and decisions

## Decision matrix

The tracker may summarize progress, but the reviewed matrix is the authority
for migration. It contains one row for each operation below:

| Operation | Required outcome |
| --- | --- |
| Discovery | Observe live advertisements and return structured, filterable devices without mutation. |
| Selection and authorization | Select one explicit opaque identifier and reject unauthorized targets. |
| Native resolution | Resolve a current-context `BLEDevice` and avoid implicit client discovery. |
| Fresh preparation | Make a controlled unprepared device usable for supported workflows. |
| Existing preparation | Reuse an already prepared device without destructive reset. |
| Persistence | Reconnect from a new client and process when later reuse is a package requirement. |
| Readiness probe | Connect, verify required Polar services, report, and disconnect within bounds. |
| Managed session | Support PMD/PFTP notifications and operations under one owner. |
| Disconnect and reconnect | Release ownership and open a later session without manual recovery. |
| Cancellation and failure | Clean partial state and preserve typed failure phase. |
| Multiple devices | Avoid hidden scans and define scanner/client coordination under concurrency. |
| Recovery | Bound retries and identify states requiring explicit operator action. |

Each row records:

- current `0.4.x` behavior as diagnostic context;
- candidate Bleak public APIs and tested Bleak version;
- exact synthetic or hardware procedure;
- operating system, Python version, adapter, and device category;
- observed result, duration, timeout phase, and cleanup state;
- private evidence location and a redacted public summary;
- verdict, limitation, rationale, reviewer, and review date.

## Sufficiency criteria

Bleak is sufficiently robust for an operation when all applicable conditions
hold:

- discovery reliably yields the intended authorized target within the
  documented timeout;
- preparation enables the supported PMD/PFTP workflow and, where required,
  later reconnect from a new client and process;
- readiness reaches the required service surface within bounded time;
- disconnect permits a subsequent managed session without a separate release
  command;
- cancellation and failure leave no connection or scanner owned by the
  abandoned operation;
- repeat runs produce typed, phase-specific failures rather than hangs or
  ambiguous state;
- both supported Linux devices pass the applicable controlled matrix.

BlueZ `Paired`, `Bonded`, and `Trusted` values may be recorded as Linux
diagnostics, but matching them is not required when operational evidence is
sufficient.

## Required experiments

### Discovery and identity

Exercise structured discovery with advertisement data and record name, RSSI,
service UUID, manufacturer identifiers where safe, and platform identifier
behavior. Cover Linux MAC values, representative macOS UUID values, and
representative Windows identifiers through injected contracts. Verify
case/format normalization, duplicate observations, missing names, changing
RSSI, filtering, authorization, and timeout.

### Resolution and connection

Compare native `BLEDevice` construction with the current string-based
`BleakClient` path. Verify that native resolution is explicit, uses the same
async context, reports a distinct not-observed failure, and does not start a
second hidden scan. Exercise service discovery, PMD/PFTP readiness, notification
startup, disconnect, and reconnect.

### Preparation

On explicitly authorized Linux hardware, exercise an unprepared device and an
already prepared device. Test the Bleak pairing/preparation path, supported
read-only PMD/PFTP access, managed disconnect, reconnect with a new client, and
reconnect from a new process. Record BlueZ state only as diagnostic evidence.
Do not remove an existing bond merely to create a test precondition without
separate authorization.

### Failure and concurrency

Exercise not observed, preparation rejected, connection timeout, missing
service, notification failure, cancellation during each lifecycle phase,
disconnect timeout, and a later recovery attempt. Use injected backends for
deterministic faults. Exercise shared scanning and two-device connection
coordination synthetically; physical two-device evidence remains governed by
SPEC-005 unless an authorized inventory is available.

### Version range

Run contracts against the minimum declared Bleak version and the newest allowed
minor release. Tighten the dependency range when behavior or public APIs do not
support one implementation across that range. Record the selected range in the
matrix before migration.

## Verdict rules

- Select **Bleak-only** when the sufficiency criteria pass using supported
  public Bleak APIs.
- Select **Bleak plus OS adapter** only for a named missing package outcome.
  The adapter must be typed, bounded, injectable, and independently tested.
- Select **Remove or redesign** when the current operation exists only to
  coordinate competing owners or expose non-portable state unnecessary to
  package workflows.
- Select **Unsupported** when safe bounded behavior cannot be demonstrated.

No lifecycle migration begins until every row has a verdict and the matrix is
reviewed as a coherent ownership model.

## Initial controlled evidence — 2026-07-29

An authorized Polar Loop Gen 2 was exercised without removing its existing
bond, resetting the device, applying FTU data, starting or stopping a
recording, or deleting device data.

The host environment was:

```text
Linux 7.0.0-28-generic x86_64
BlueZ 5.72
Python 3.13.14
Bleak 3.0.2
```

The device began paired, bonded, trusted, and disconnected according to BlueZ.
These flags were recorded only to establish the initial condition.

| Experiment | Result | Evidence and limitation |
| --- | --- | --- |
| Structured Bleak discovery | Passed | `BleakScanner.discover(return_adv=True)` observed the authorized target in 10.176 seconds with matching identifier, local name, RSSI, seven advertised service UUIDs, one manufacturer-data entry, and native backend details. Advertisement payloads and the identifier were not retained. |
| Existing-device preparation | Passed provisionally | `BleakClient(BLEDevice, pair=True)` connected in 6.958 seconds, exposed PMD and PFTP, and ended disconnected. This proves reuse of the existing preparation only; it does not prove fresh preparation. |
| Explicit resolution and reconnect | Passed provisionally | A newly resolved `BLEDevice` was obtained in 0.555 seconds. Its client connected in 5.384 seconds, exposed PMD and PFTP, and ended disconnected. |
| Not-observed lookup | Passed | A one-second targeted lookup for a nonexistent address returned `None` in 1.081 seconds. |
| New-process reconnect | Passed provisionally | Two separate Python processes independently resolved, connected, verified PMD/PFTP, and disconnected. |
| Scanner cancellation and recovery | Passed provisionally | A targeted scan cancelled in 0.181 seconds and a subsequent targeted resolution found the authorized device. |
| Connection cancellation and recovery | Passed with latency requiring follow-up | Cancellation propagated after 5.331 seconds; the client was already disconnected, explicit cleanup was idempotent, and a subsequent client connected, verified PMD/PFTP, and disconnected. Repeat runs must determine the cancellation budget. |
| Repeated connect/disconnect | Passed provisionally | Five sequential native-resolution/client cycles, alternating `pair=True` and `pair=False`, all verified PMD/PFTP and ended disconnected. Per-cycle elapsed time was 4.701–6.975 seconds. Longer-duration and concurrent testing remain open. |
| Managed PMD/PFTP workflow | Passed | The existing live matrix completed two managed sessions, PMD availability/status reads, raw recording listing, and reconnect. |
| Passive PFTP workflow | Passed | The existing live matrix listed, fetched, hash-stored, verified, and decoded one daily-summary file without device mutation. |
| Cleanup dry-run lifecycle | Passed with no eligible deletion evidence | The dry-run deleted nothing; all selected candidates were blocked by missing local verification. This confirms non-deletion and clean lifecycle only. |

After all probes, BlueZ again reported the device paired, bonded, trusted, and
disconnected. No raw identifier, advertisement payload, capture, profile, or
hardware log was added to the repository.

The non-reset discovery, native reconnect, cancellation, and recovery subset is
reproducible through:

```bash
POLAR_BLE_SPEC009=1 \
POLAR_BLE_LIVE_MAC="<authorized identifier>" \
pytest -q -s tests/live/test_spec009_bleak_experiments.py
```

The initial controlled run passed both tests in 35.88 seconds, including three
native-resolution connection cycles. The test module always uses `pair=False`
and performs no bond removal, device reset, FTU write, recording control,
payload fetch, or deletion.

### Provisional conclusions

- Structured Bleak discovery is a **Bleak-only candidate** for this Linux
  environment. Repeatability, version-range, and cross-platform contracts
  remain open.
- Explicit native resolution, service readiness, managed disconnect, and
  same-host reconnect are **Bleak-only candidates**.
- Five sequential connect/disconnect cycles and two separate-process cycles
  completed without stale ownership. Longer-duration and concurrent testing
  remain open.
- Scanner and connection cancellation recovered without stale ownership in one
  controlled run. The observed connection-cancellation latency requires a
  defined timeout budget and repetition before a verdict.
- Existing-device preparation with `pair=True` is a **Bleak-only candidate**.
  Fresh preparation remains untested because it would require an explicitly
  authorized unprepared/reset state.
- The current package's PMD, PFTP, passive-fetch, and dry-run paths operate
  successfully across managed Bleak sessions on this device.
- No final verdict is assigned until the remaining decision-matrix evidence
  and second supported Linux device coverage are complete.
