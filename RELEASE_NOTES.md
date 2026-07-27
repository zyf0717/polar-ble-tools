# polar-ble-tools 0.3.0

`0.3.0` completes the core BLE recording, retrieval, and guarded-cleanup
surface for Polar Loop Gen 2 and Polar Verity Sense on Linux/BlueZ.

## Recording operations

- Added public Python APIs and `polar-ble raw` commands for recording
  capabilities, status, settings, start, stop, triggers, and device disk space.
- Added exact-path raw REC fetch with grammar validation, atomic no-clobber
  publication, size, and SHA-256 metadata.
- Recording stop waits for bounded inactive status.

## Passive collection and cleanup

- Added complete passive PFTP synchronization lifecycle handling.
- Added explicit skip/overwrite collection policy.
- Added guarded delete-after-collect with latest-date and unknown-date
  retention.
- Added date/domain-bounded cleanup, local-only dry-run, and append-only
  deletion audit records.
- BLE transport failures abort the workflow; attempted deletion remains
  auditable.

## Python contract

- Raw and passive listing/result collections are immutable tuples.
- Collection and deletion outcomes use project-owned `StrEnum` values.
- `to_jsonable()` and CLI output retain stable strings and JSON lists.
- Raw and passive stores share streaming SHA-256 and atomic/JSONL mechanics
  while keeping separate eligibility and audit policies.

## Compatibility and boundaries

The supported devices are Polar Loop Gen 2 and Polar Verity Sense, limited to
the operations recorded in the [compatibility matrix](docs/compatibility.md).
Charging-state recording rejection is a typed device-state response; passive
PFTP access may remain available.

Verity Sense passive activity, sleep, wellness, and related domains are not
claimed. Encrypted REC decoding, batch decoding, Linux aarch64 decoder support,
two-device hardware certification, and forced radio-loss recovery are not
`0.3.0` capabilities.

The distribution includes no Polar SDK source, generated SDK artifacts, real
recordings, device inventories, or compiled decoder binary.
