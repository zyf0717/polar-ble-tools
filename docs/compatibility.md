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

## Other devices

No other device is confirmed for `0.1.1`. Devices exposing compatible PMD and
PFTP services are expected to support some operations, but should be treated as
untested until their capability matrix passes on protected hardware.

## Unsupported or incomplete behavior

- Structured `.REC` decoding is not included.
- Multi-device locking is covered by unit tests but not validated with two
  physical devices.
- Forced Bluetooth/radio-loss recovery is not validated.
- SDK revisions other than the pinned revision are diagnostic overrides and
  carry no compatibility guarantee.
- Device features absent from PMD/PFTP or unknown `.BPB` paths are reported as
  unsupported.

SDK contracts use separately licensed input and are not part of ordinary public
CI. A skipped SDK or hardware job is not evidence of device compatibility.
