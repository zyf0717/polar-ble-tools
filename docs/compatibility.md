# Compatibility

## Supported devices

`0.3.2` supports Polar Loop Gen 2 and Polar Verity Sense on Linux/BlueZ within
the controlled capability boundaries below.

## Polar Loop Gen 2

Controlled checks covered:

- discovery, pairing, bonding, trust, connection handoff, and reconnect;
- PMD availability and status, plus accelerometer recording start/stop;
- PFTP raw `.REC` listing, retrieval, size checks, SHA-256 storage, and cleanup
  dry-run;
- FTU profile application, status, and device settings;
- passive activity-sample, daily-summary, and skin-temperature `.BPB` retrieval
  and hash storage;
- daily-summary BPB decoding with a verified local schema cache.

Controlled Linux aarch64/BlueZ validation confirmed discovery, durable pairing
and bonding, and FTU profile application for Polar Loop Gen 2. This evidence
does not extend the x86_64-only REC-decoder support claim.

In a controlled 2026-07-27 observation, the target advertised ACC, HR, PPG, PPI,
and SKIN_TEMPERATURE as available offline-recording types. Availability is not
evidence that recording start/stop works for every advertised type; ACC remains
the only Loop Gen 2 type with controlled start/stop evidence.

The same observation retrieved and SHA-256-verified six logical days each of
activity-sample, daily-summary, and skin-temperature BPB files. Only the
daily-summary file was decoded. Raw retrieval therefore does not establish
schema-decoding support for activity samples or skin temperature. No sleep,
nightly-recharge, or autos file was present in that bounded lookback; absence is
not evidence that those domains are unsupported.

The cleanup check did not delete device data. Reconnect required bounded retries
after repeated BlueZ activity and completed within the configured operation
timeout.

Interpret cleanup outcomes by status rather than the test process exit code. A
result with selected entries but `dry_run=0` and only blocked entries confirms
the local-verification guard and non-deletion behavior; it does not exercise an
eligible cleanup dry-run. Eligible dry-run evidence requires at least one
verified local copy to reach the `dry_run` status.

When a device is in its charging state, offline recording start may be rejected
with the PMD typed response
`ERROR_DEVICE_IN_CHARGER`. This is a valid device-state result, not a BLE
transport failure. Passive PFTP collection can remain available in this state.
Recording-control callers can inspect `PmdResponseError.response_code` to
distinguish this condition.

## Polar Verity Sense

Controlled Linux/BlueZ validation confirmed PMD availability and inactive
status reporting for ACC, GYRO, HR, MAGNETOMETER, PPG, and PPI. Bounded
offline-recording start/stop and exact raw REC retrieval were exercised for all
six types; the resulting files were size- and SHA-256-verified locally.

Passive collection over the canonical domains returned no files; Verity Sense
passive activity, sleep, wellness, or related domain support is not claimed.
No destructive deletion was performed.

Other devices exposing compatible PMD and PFTP services should be treated as
untested until their capability matrix passes on controlled hardware.

## Structured REC decoding

REC compatibility is experimental and requires private fixture-contract
evidence for the exact SDK commit, source digest, output digest, count, and
timestamp policy. The current claimed adapter categories are ACC, HR, PPG, PPI,
skin temperature, magnetometer, and gyroscope; claims remain unsupported until
the local contract manifest verifies each category. Encrypted recordings are
unsupported. PPI envelope timestamps are intentionally suppressed for every
device pending validated SDK semantics; the raw SDK `time_stamp` remains in the
payload.

## Unsupported or incomplete behavior

- Structured `.REC` decoding is local-only and limited as above.
- Batch and protected REC decoding are not `0.3.2` capabilities.
- The optional REC decoder is currently limited to Linux x86_64.
- Multi-device locking is covered by unit tests but not validated with two
  physical devices.
- Forced Bluetooth/radio-loss recovery is not validated.
- SDK revisions other than the pinned revision are diagnostic overrides and
  carry no compatibility guarantee.
- Device features absent from PMD/PFTP or unknown `.BPB` paths are reported as
  unsupported.

SDK contracts use separately licensed input and are not part of ordinary public
CI. A skipped SDK or hardware job is not evidence of device compatibility.
