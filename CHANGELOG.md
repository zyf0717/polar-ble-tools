# Changelog

All notable changes to this project are documented here.

## Unreleased

### Added

- Added stable typed collection/deletion statuses and immutable public
  collection results for raw and passive BLE operations.

### Changed

- Consolidated streaming local-file SHA-256 verification across raw and passive
  stores while retaining their separate eligibility and audit rules.
- Narrowed SPEC-003 to release-oriented core BLE operations; optional decoder
  expansion and protected compatibility certification now live in SPEC-004 and
  SPEC-005.

## 0.2.1 — 2026-07-27

### Documentation

- Reframed the package description around offline, device-resident data
  collection and delayed local retrieval.
- Clarified that data collection and retrieval do not require Polar Flow.
- Expanded package keywords for offline recording, device storage, and wearable
  data collection.

## 0.2.0 — 2026-07-26

- Added optional local REC decoder lifecycle and `polar-ble rec` commands.
- Added streaming JSONL protocol validation, digest-verified runtimes, private
  output publication, bounded diagnostics, and process-group timeout cleanup.
- Added `doctor()` and direct FTU workflow APIs, plus top-level passive-file
  collection exports.
- Added explicit CLI and Python API references.
- Removed obsolete REC build spike scripts and consolidated the former spec
  material into shipping documentation.

Known limitations: encrypted recordings and categories without local contract
evidence remain unsupported; PPI envelope timestamps are absent for every
device until their SDK semantics are validated.

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
