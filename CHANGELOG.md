# Changelog

All notable changes to this project are documented here.

## Unreleased

- Added the optional local REC decoder sidecar and `polar-ble rec` commands.
- Added verified local decoder build, activation, status, verification, removal,
  and `doctor` readiness reporting.
- Added experimental local REC decoding infrastructure and protocol validation.
- Added runtime-file allowlisting/digest verification, bounded sidecar output,
  timeout cleanup, Gradle dependency locking, and opt-in local corpus contracts.

Known limitations: encrypted recordings and categories without local contract
evidence remain unsupported; Verity Sense PPI timestamp interpretation remains
an experimental compatibility issue.

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
