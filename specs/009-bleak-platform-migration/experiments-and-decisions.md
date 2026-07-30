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

The initial controlled run passed both default tests in 35.88 seconds,
including three native-resolution connection cycles. Those default tests
always use `pair=False` and perform no bond removal, device reset, FTU write,
recording control, payload fetch, or deletion. The separately gated fresh
preparation test added below uses `pair=True`.

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

## Downstream Loop Gen 2 evidence — 2026-07-29

The same authorized device was used to extend coverage beyond connection
readiness. Initial discovery and pairing were not exercised. No bond reset,
device reset, or device-file deletion was performed. The initial downstream
run inspected existing FTU state; a subsequent, separately authorized run
applied the tracked documentation profile described below.

| Workflow | Result | Evidence and limitation |
| --- | --- | --- |
| FTU state and configuration reads | Passed | FTU reported complete; physical configuration, user-device settings, and setup diagnostics were read successfully. Only field counts were logged; values were not retained. |
| PMD/PFTP status reads | Passed | Five recording types and five status entries were observed; trigger configuration, disk-space invariants, and raw recording listing succeeded. No configuration was changed. |
| ACC recording start/stop | Passed | One inactive ACC recording was started with device-reported minimum settings, confirmed active, recorded for four seconds, and stopped in a bounded `finally`-guarded workflow. |
| REC materialization and retrieval | Passed | A later managed session observed the new `ACC0` recording, fetched it, persisted it atomically beneath the ignored local root, and verified its manifest size and SHA-256. |
| Eligible cleanup dry-run | Passed | The newly verified recording was selected with status `dry_run`; the deletion count remained zero and the device file was retained. |
| FTU application and settings write | Passed with explicitly authorized documentation input | The maintainer approved `docs/ftu-profile.example.json` as sound hardware-test input. `apply_ftu()` completed, wrote its settings patch, and 14 declared physical/settings fields were read back and verified without logging their values. |

The final postcondition check reported no active recordings and a disconnected
BlueZ device while preserving the existing paired, bonded, and trusted state.

The reusable harness is:

```bash
POLAR_BLE_SPEC009=1 \
POLAR_BLE_LIVE_MAC="<authorized identifier>" \
pytest -q -s tests/live/test_spec009_device_workflows.py
```

The FTU and PMD/PFTP read tests are non-mutating. The ACC test additionally
requires `POLAR_BLE_SPEC009_MUTATING=1`; it creates and retains one recording
and still performs cleanup only as a dry-run.

Applying the tracked documentation profile is separately gated:

```bash
POLAR_BLE_SPEC009=1 \
POLAR_BLE_SPEC009_FTU_APPLY=1 \
POLAR_BLE_LIVE_MAC="<authorized identifier>" \
pytest -q -s \
  tests/live/test_spec009_device_workflows.py::test_spec009_apply_documented_ftu_profile
```

These results establish representative FTU-read, PMD-control, PFTP listing,
raw retrieval, local verification, and guarded-cleanup behavior across managed
sessions. The documented FTU input is now verified on the authorized Loop Gen
2. Actual deletion remains outside the current authorization.

## Fresh Loop Gen 2 preparation evidence — 2026-07-30

The maintainer reset the authorized Loop Gen 2 and explicitly authorized
removal of its exact host-side BLE cache record. The device was disconnected
before each removal. The host-side setup and probes did not change an
adapter-wide cache, another device record, FTU data, recordings, or device
files.

The host environment remained Bleak 3.0.2, BlueZ 5.72, Python 3.13.14, and
Linux x86_64.

| Experiment | Result | Evidence and limitation |
| --- | --- | --- |
| Exact BlueZ record removal | Passed | The prior paired, bonded, trusted, disconnected record was removed and `bluetoothctl info` reported the exact device unavailable before the fresh probe. This established the uncached host precondition; removal itself is test setup, not a proposed package workflow. |
| Fresh Bleak preparation without an authentication agent | Failed; missing dependency identified | Structured Bleak resolution found the reset device, but `BleakClient(BLEDevice, pair=True)` failed in 11.39 seconds with `org.bluez.Error.AuthenticationFailed`. BlueZ reported that no agent was available for authentication request type 2. The failed attempt ended unpaired, unbonded, trusted, and disconnected; Bleak had set trust before requesting pairing. |
| First agent-assisted retry | Failed and recovered | With an ephemeral BlueZ `KeyboardDisplay` agent requested, the first bounded retry failed in 7.84 seconds with `org.bluez.Error.ConnectionAttemptFailed: Page Timeout`. It did not reach authentication and ended unpaired and disconnected. The exact record was removed again before the controlled retry. |
| Fresh Bleak preparation with a confirmed default authentication agent | Passed | After confirming the ephemeral `KeyboardDisplay` agent was registered and default, the exact device record was absent. The same Bleak probe resolved the device, paired with `pair=True`, exposed PMD and PFTP, disconnected, re-resolved it, reconnected through a new `pair=False` client, verified services, and disconnected. The two-connection probe passed in 22.65 seconds. |
| New-process persistence without an agent | Passed | After the agent exited, a separate pytest process performed structured discovery and three `pair=False` client cycles. All exposed PMD/PFTP and disconnected; the run passed in 36.03 seconds with seven advertised services. |
| Durable postcondition | Passed as Linux diagnostic evidence | BlueZ reported paired, bonded, trusted, unblocked, and disconnected after the agent had exited and all Bleak reconnects completed. |

The separately gated fresh-preparation probe is:

```bash
POLAR_BLE_SPEC009=1 \
POLAR_BLE_SPEC009_FRESH_PREPARATION=1 \
POLAR_BLE_LIVE_MAC="<authorized identifier>" \
pytest -q -s \
  tests/live/test_spec009_bleak_experiments.py::test_spec009_fresh_bleak_preparation
```

On Linux this command assumes the exact host bond is absent, the device is in
its fresh pairing window, and a suitable BlueZ authentication agent is already
registered. The harness itself does not remove bonds or register an agent.

### Fresh-preparation conclusion

- Fresh Loop Gen 2 preparation is a **Bleak plus OS adapter candidate**, not a
  Bleak-only candidate on a Linux host without an existing authentication
  agent. Bleak owned discovery, trust request, pairing request, service
  readiness, disconnect, and reconnect, but did not supply the BlueZ
  authentication-agent callback required by this device.
- The demonstrated missing outcome is narrowly scoped to Linux authentication
  agent registration and bounded interaction. Any adapter must be typed,
  injectable, independently tested, and limited to that OS-owned concern; it
  must not own scanning, connection, PMD, or PFTP.
- Once prepared, discovery, readiness, disconnect, same-process reconnect, and
  new-process reconnect remained Bleak-only and did not require the agent.
- A transient `Page Timeout` remains part of the recovery matrix. One bounded
  clean-precondition retry succeeded; retry limits and typed failure mapping
  remain to be decided.
- macOS and Windows preparation behavior remains pending and must not inherit
  this Linux-specific mechanism.

## Post-reset FTU and Bleak E2E evidence — 2026-07-30

After fresh pairing, BlueZ reported the authorized Loop Gen 2 paired, bonded,
trusted, and disconnected. A Bleak-backed `ftu_status()` call reported
`false`, confirming that successful BLE preparation did not imply completed
Polar first-time use.

The maintainer-authorized `docs/ftu-profile.example.json` was then applied
through the Bleak-backed FTU workflow. FTU completion and all 14 declared
physical/settings fields were read back and verified in 40.22 seconds without
logging their values.

The post-FTU Bleak E2E passed:

| Workflow | Result |
| --- | --- |
| FTU/config/settings diagnostics | Passed; FTU complete, seven settings fields and four diagnostic fields observed. |
| PMD/PFTP readiness | Passed; five available recording types, five status entries, trigger configuration, disk-space invariants, and raw listing verified. |
| ACC recording lifecycle | Passed; one short ACC recording was started, observed active, stopped, and materialized as `ACC0`. |
| Raw retrieval and local verification | Passed; the new recording was fetched, atomically persisted beneath the ignored local root, and verified by manifest size and SHA-256. |
| Guarded cleanup | Passed in dry-run mode; the verified recording was selected, zero device files were deleted, and the recording was retained. |

The combined E2E run passed three tests with one independently gated FTU-apply
test skipped in 49.12 seconds. Final independent checks reported FTU complete,
zero active recordings, and paired, bonded, trusted, unblocked, disconnected
BlueZ state. The authentication agent was not required after fresh pairing;
all FTU, PMD, PFTP, recording, retrieval, and verification operations used the
package's Bleak transport.
