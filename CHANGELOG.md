# Changelog

All notable changes to this project are documented here.

## 0.2.0 — 2026-07-26

- Added the optional local REC decoder sidecar and `polar-ble rec` commands.
- Added verified local decoder build, activation, status, verification, removal,
  and `doctor` readiness reporting.
- Added validated JSONL decoding for the exercised unencrypted Loop Gen 2 and
  Verity Sense ACC, HR, PPG, PPI, skin-temperature, magnetometer, and gyroscope
  recordings.
- Added runtime-file allowlisting/digest verification, bounded sidecar output,
  timeout cleanup, Gradle dependency locking, and opt-in local corpus contracts.

Known limitations: encrypted recordings and unexercised SDK record categories
remain unsupported; Verity Sense PPI timestamp interpretation remains flagged
as an experimental compatibility issue.

## 0.1.1 — 2026-07-25

- Made protected live-device tests opt-in.

## 0.1.0 — 2026-07-25

- Added the `polar-ble` CLI for Linux/BlueZ discovery, authorized pairing,
  connection, PMD/PFTP operations, raw `.REC` collection, passive `.BPB`
  collection, storage, and guarded cleanup.
- Added FTU profile validation, application, status, diagnostics, and device
  settings operations.
- Added optional local SDK schema installation, inspection, generation,
  verification, activation, and removal.
- Added BPB decoding through verified local schemas.
- Added SDK-free tests, SDK contract tests, package-content auditing, and
  protected live-device tests.

Known limitations: structured `.REC` decoding, forced radio-loss recovery, and
multi-device hardware validation are not supported release capabilities.
