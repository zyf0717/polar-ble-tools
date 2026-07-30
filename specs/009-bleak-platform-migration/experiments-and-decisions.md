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
applied the tracked Loop Gen 2 documentation profile described below.

| Workflow | Result | Evidence and limitation |
| --- | --- | --- |
| FTU state and configuration reads | Passed | FTU reported complete; physical configuration, user-device settings, and setup diagnostics were read successfully. Only field counts were logged; values were not retained. |
| PMD/PFTP status reads | Passed | Five recording types and five status entries were observed; trigger configuration, disk-space invariants, and raw recording listing succeeded. No configuration was changed. |
| ACC recording start/stop | Passed | One inactive ACC recording was started with device-reported minimum settings, confirmed active, recorded for four seconds, and stopped in a bounded `finally`-guarded workflow. |
| REC materialization and retrieval | Passed | A later managed session observed the new `ACC0` recording, fetched it, persisted it atomically beneath the ignored local root, and verified its manifest size and SHA-256. |
| Eligible cleanup dry-run | Passed | The newly verified recording was selected with status `dry_run`; the deletion count remained zero and the device file was retained. |
| FTU application and settings write | Passed with explicitly authorized documentation input | The maintainer approved `docs/loop-gen2-ftu-profile.example.json` as sound hardware-test input. `apply_ftu()` completed, wrote its settings patch, and 14 declared physical/settings fields were read back and verified without logging their values. |

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

Applying the tracked Loop Gen 2 documentation profile is separately gated:

```bash
POLAR_BLE_SPEC009=1 \
POLAR_BLE_SPEC009_FTU_APPLY=1 \
POLAR_BLE_SPEC009_FTU_FAMILY=POLAR_LOOP_GEN2 \
POLAR_BLE_LIVE_MAC="<authorized identifier>" \
pytest -q -s \
  tests/live/test_spec009_device_workflows.py::test_spec009_apply_loop_gen2_ftu_profile
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

The maintainer-authorized `docs/loop-gen2-ftu-profile.example.json` was then
applied through the Bleak-backed FTU workflow. FTU completion and all 14
declared physical/settings fields were read back and verified in 40.22 seconds
without logging their values.

The same profile was later reapplied twice after FTU was already complete.
Both applications completed through Bleak, and each read-back matched all 14
declared fields, in 35.71 and 39.94 seconds respectively. This establishes a
repeat-safe semantic outcome on the tested Loop Gen 2, not strict no-write
idempotence: the current workflow always writes the local time, physical data,
user identifier, and settings, and profiles without an explicit `device_time`
receive the current time when parsed.

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

## Host-unpaired Verity Sense evidence — 2026-07-30

The authorized Verity Sense began paired, bonded, trusted, and disconnected.
The maintainer explicitly authorized unpairing before repeating applicable
SPEC-009 evidence. `BleakClient.unpair()` removed the exact BlueZ device record,
and a subsequent host-state check reported the device unavailable.

The initial run did not hardware-reset the device and therefore established
only the uncached and unpaired host path. A later factory-reset extension below
established the device-side reset path.

| Experiment | Result | Evidence and limitation |
| --- | --- | --- |
| Exact Bleak unpair | Passed | Bleak's supported Linux `unpair()` operation removed the disconnected Verity BlueZ object without `bluetoothctl` removal or changes to other device records. |
| Fresh host preparation without an authentication agent | Failed; missing dependency confirmed | Bleak resolved the uncached device, set trust, and requested pairing. The probe failed in 3.38 seconds with `org.bluez.Error.AuthenticationFailed`; BlueZ reported no agent for authentication request type 2. Final failed-attempt state was unpaired, unbonded, trusted, and disconnected. |
| Failed-attempt cleanup | Passed | A second exact Bleak `unpair()` removed the residual trusted device object before retry. |
| Agent-assisted Bleak preparation | Passed | With an ephemeral default BlueZ `KeyboardDisplay` agent, Bleak paired, exposed PMD/PFTP, disconnected, then re-resolved and reconnected with a new client. The two-connection probe passed in 9.26 seconds. |
| New-process persistence without an agent | Passed | After the agent exited, a separate process completed structured discovery and three Bleak-only PMD/PFTP-ready connection cycles in 23.61 seconds; eight advertised services were observed. |
| Cancellation cleanup and recovery | Passed | Scanner/connect cancellation cleanup and a later successful Bleak recovery completed in 7.17 seconds without stale ownership. |
| Read-only PMD/PFTP workflow | Passed | Six available recording types and six status entries were observed; trigger configuration, disk-space invariants, and raw listing passed in 11.21 seconds. |
| Durable postcondition | Passed as Linux diagnostic evidence | FTU remained complete. BlueZ reported paired, bonded, trusted, unblocked, and disconnected, with no authentication agent remaining. |

No FTU data, recording state, payload, or device file was changed. No device
identifier or hardware log was added to the repository.

### Factory-reset extension

The maintainer then performed Polar's documented Flow factory reset and did
not set the sensor up again. The stale disconnected Linux bond was removed with
exact Bleak `unpair()` before testing.

After reset, the BLE identifier remained stable but the pre-setup advertised
name changed from Verity Sense to `Polar Sense`. The sensor was not advertising
immediately after reset; after a physical power-on it appeared with the
expected Polar service shape. No inventory identifier change was required.

| Experiment | Result | Evidence and limitation |
| --- | --- | --- |
| Factory-reset preparation without an authentication agent | Failed; missing dependency reconfirmed | The uncached device resolved after power-on, then `BleakClient(BLEDevice, pair=True)` failed in 1.78 seconds with `org.bluez.Error.AuthenticationFailed`. BlueZ again reported no agent for authentication request type 2. The attempt ended unpaired, unbonded, trusted, and disconnected. |
| Failed-attempt cleanup | Passed | Exact Bleak `unpair()` removed the residual trusted object before retry. |
| Factory-reset agent-assisted preparation | Passed | With the ephemeral default BlueZ `KeyboardDisplay` agent, Bleak paired, exposed PMD/PFTP, disconnected, and reconnected with a new client. The two-connection probe passed in 8.98 seconds. |
| Agent-free new-process persistence | Passed | After the agent exited, a separate process completed structured discovery and three PMD/PFTP-ready Bleak connection cycles in 22.80 seconds with eight advertised services. |
| Factory-reset and durable postconditions | Passed | Bleak reported FTU incomplete. BlueZ reported paired, bonded, trusted, unblocked, and disconnected, with no authentication agent remaining. |

No FTU profile was applied and no recording or device file was changed during
the factory-reset pairing experiment.

### Post-reset setup mismatch and E2E extension

The maintainer then authorized the same tracked
`docs/loop-gen2-ftu-profile.example.json` input and downstream recording E2E
used for Loop Gen 2.

Verity FTU did not complete. Two bounded applications each timed out at 60.16
seconds while waiting for the PFTP response to the physical-configuration
write. Physical configuration was present after the first attempt, but the FTU
completion flag remained false and settings verification was never reached.
Both attempts disconnected cleanly. After the same failure repeated, no further
FTU writes were attempted.

Subsequent device-specific review showed that this was not a valid Verity FTU
procedure. Polar's documented Verity setup exposes wear location and default
pool length rather than the Loop physical profile. The current package model
supports wear location in `UDEVSET.BPB` but has no pool-length field or verified
device-file contract. A read-only Verity settings check already reported
`UPPER_ARM_LEFT`. The verified local SDK descriptors contain a separate
swimming-pool structure, but no write path is inferred from that schema alone.

Independent workflows remained available:

| Workflow | Result |
| --- | --- |
| PMD/PFTP readiness | Passed in 7.03 seconds; six available recording types, six status entries, trigger configuration, disk-space invariants, and raw listing were verified. |
| ACC recording lifecycle | Passed; one short ACC recording was started, observed active, stopped, and materialized. |
| Raw retrieval and local verification | Passed; the new ACC recording was fetched, atomically persisted beneath the ignored local root, and verified by manifest size and SHA-256. |
| Guarded cleanup | Passed in dry-run mode; the verified recording was selected, zero files were deleted, and the device file was retained. The combined recording E2E passed in 19.86 seconds. |
| Final postconditions | Passed; FTU remained incomplete, physical configuration remained present, zero recordings were active, and BlueZ reported paired, bonded, trusted, unblocked, and disconnected. |

This is evidence that Verity PMD/PFTP/raw workflows do not require the
Loop-style FTU marker. The timed-out physical-data write is retained as negative
evidence against applying the current generic FTU workflow to Verity; it is not
evidence that Verity's actual setup is unsupported. At this experiment point,
Verity setup remained unmodeled pending a device-specific contract.

### Verity Sense conclusion

- Verity Sense independently confirms the Loop Gen 2 result that fresh
  Linux-host preparation is a **Bleak plus OS adapter candidate** because
  request-type-2 authentication requires a registered BlueZ agent.
- Bleak `unpair()` is sufficient for exact Linux host-record removal and is a
  candidate replacement for the current `bluetoothctl remove` test/setup path.
- After preparation, discovery, readiness, cancellation recovery, disconnect,
  and new-client/new-process reconnect are Bleak-only candidates on both
  controlled Linux devices.
- Factory-reset Verity evidence confirms that the Linux agent requirement was
  not an artifact of a retained device-side bond.
- The Loop physical-data/user-identifier FTU workflow is inapplicable to
  Verity. Verity instead has a device-specific system/local-time and
  wear-location path, while its Bleak-backed PMD/PFTP/ACC/retrieval workflow
  passes independently.

### Sample-backed Verity setup probe

The maintainer then explicitly authorized applying
`docs/verity-sense-ftu-profile.example.json` through Bleak. At the start of this
probe, Verity reported its setup marker complete and its wear location already
matched `UPPER_ARM_LEFT`.

Read-only file-system inspection identified `/U/USENSET.BPB` as the only
additional setup-related candidate outside the known `UDEVSET.BPB` and
`PREFS.BPB` files. The device rejected reading it with PFTP
`OPERATION_NOT_PERMITTED`. The verified SDK exposes `PbSwimmingPoolInfo`, but
contains neither the protected file's root schema nor a pool-length API or
write path. A standalone swimming-pool structure therefore cannot safely be
written or merged into that multi-setting file.

The supported wear-location component was applied through
`update_user_device_settings()` over the package's Bleak transport. A separate
Bleak session read it back as `UPPER_ARM_LEFT`; the setup marker remained
complete. No pool-length write was attempted, so this is a **partial sample
application**, not successful Verity FTU. Final checks reported zero active
recordings and paired, bonded, trusted, unblocked, disconnected BlueZ state.

The maintainer subsequently selected the verified subset as the package's
current Verity FTU contract. The tracked sample was narrowed to
`device_family` and `device_location`; `VeritySenseFtuProfile` and
`load_ftu_profile()` now validate and dispatch it. Pool length and all other
fields are rejected during offline validation. This makes the supported
wear-location profile executable without broadening the protected pool-settings
contract.

The exact narrowed tracked sample then passed the public CLI apply path on the
authorized Verity Sense. The command reported FTU applied and settings updated.
A separate Bleak session loaded the same profile and verified
`UPPER_ARM_LEFT`; the setup marker was complete, zero recordings were active,
and BlueZ remained paired, bonded, trusted, unblocked, and disconnected. The
reproducible live gate is:

```bash
POLAR_BLE_SPEC009=1 \
POLAR_BLE_SPEC009_FTU_APPLY=1 \
POLAR_BLE_SPEC009_FTU_FAMILY=POLAR_VERITY_SENSE \
POLAR_BLE_LIVE_MAC="<authorized identifier>" \
pytest -q -s \
  tests/live/test_spec009_device_workflows.py::test_spec009_apply_verity_sense_ftu_profile
```

### Verity Sense time probe

The maintainer separately authorized updating the existing Verity Sense clock.
Through a managed Bleak session, the existing setup client sent
`SET_SYSTEM_TIME` followed by `SET_LOCAL_TIME` using the current timezone-aware
host time. Both operations succeeded; the device did not require the
unsupported-system-time fallback. `GET_LOCAL_TIME` read-back preserved the
host UTC+08:00 offset and matched the requested value within 0.778 seconds.

A second read in a new managed Bleak session confirmed that the device clock
continued to advance: device time advanced 6.000 seconds while host time
advanced 6.360 seconds. PFTP query and connection latency must not be counted
as clock drift by comparing only against a timestamp captured after the query.
Future tests should compare the first read with the exact requested value and
compare subsequent device-time advancement with elapsed host time.

The final host postcondition remained paired, bonded, trusted, unblocked, and
disconnected. No recording or profile file was changed. This establishes
Bleak-backed system/local time setup as a Verity workflow candidate. Time is
runtime state derived immediately after connection from the timezone-aware host
clock; it does not belong in the Verity profile JSON.

### Integrated Verity FTU path

The verified time operation was then integrated with wear-location setup as a
first-class `PolarSetupClient` path. Both public entry points dispatch
`VeritySenseFtuProfile` to the same sequence within one managed Bleak session:

1. capture current timezone-aware host time after connection readiness;
2. send `SET_SYSTEM_TIME` and `SET_LOCAL_TIME`;
3. read, patch, and write wear location in `UDEVSET.BPB`;
4. disconnect through managed cleanup.

The path never writes Loop `PHYSDATA.BPB` or `USERID.BPB`. A time failure
reports that clock state may be partial; a later settings failure reports a
partial FTU after time setup. `GET_LOCAL_TIME` parsing and readback are exposed
through the setup client for verification.

The family-gated public Python hardware test passed in 20.78 seconds and
verified both runtime time and `UPPER_ARM_LEFT` in subsequent managed sessions.
The public CLI path then independently applied the documented Verity profile;
a read-only session verified both outcomes with device time 1.608 seconds
outside the host query interval, within the five-second PFTP-latency bound.
Both runs ended paired, bonded, trusted, unblocked, and disconnected. No Loop
setup file, recording, or profile file was changed.
