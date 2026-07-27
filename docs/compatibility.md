# Compatibility

## Confirmed device

Polar Loop Gen 2 was validated on Linux with BlueZ on 2026-07-25. The controlled
checks covered:

- discovery, pairing, bonding, trust, connection handoff, and reconnect;
- PMD availability, status, and accelerometer recording start/stop;
- PFTP raw `.REC` listing, retrieval, size checks, SHA-256 storage, and cleanup
  dry-run;
- FTU profile application, status, and device settings;
- passive daily-summary `.BPB` retrieval and hash storage;
- daily-summary BPB decoding with a verified local schema cache.

The cleanup check did not delete device data. Reconnect required bounded retries
after repeated BlueZ activity and completed within the configured operation
timeout.

When a device is in its charging state, offline recording start may be rejected
with the PMD typed response
`ERROR_DEVICE_IN_CHARGER`. This is a valid device-state result, not a BLE
transport failure. Passive PFTP collection can remain available in this state.
Recording-control callers can inspect `PmdResponseError.response_code` to
distinguish this condition.

## Verity Sense

Controlled Linux/BlueZ validation confirmed PMD availability and inactive
status reporting for ACC, GYRO, HR, MAGNETOMETER, PPG, and PPI. Bounded
offline-recording start/stop and exact raw REC retrieval were exercised for
ACC, GYRO, MAGNETOMETER, PPG, and HR; the resulting files were size- and
SHA-256-verified locally.

PPI start was observed but did not produce an REC file in this run, so PPI REC
output is not yet claimed. Passive collection over the canonical domains
returned no files; Verity Sense passive activity, sleep, wellness, or related
domain support is not claimed. No destructive deletion was performed.

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
- Multi-device locking is covered by unit tests but not validated with two
  physical devices.
- Forced Bluetooth/radio-loss recovery is not validated.
- SDK revisions other than the pinned revision are diagnostic overrides and
  carry no compatibility guarantee.
- Device features absent from PMD/PFTP or unknown `.BPB` paths are reported as
  unsupported.

SDK contracts use separately licensed input and are not part of ordinary public
CI. A skipped SDK or hardware job is not evidence of device compatibility.
