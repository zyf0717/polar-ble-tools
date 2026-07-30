# Changelog

All notable changes to this project are documented here.

## Unreleased

### Added

- Scoped FTU profiles by device family and added an executable Verity Sense
  wear-location profile that rejects unsupported pool-length input.

## 0.4.1 — 2026-07-29

### Documentation

- Reworked the root quick start into explicit first-time setup, passive BPB,
  and offline REC workflows.
- Promoted raw REC recording and collection to a first-class workflow shared
  by Polar Loop Gen 2 and Polar Verity Sense.
- Added the complete common ACC sequence for inspecting settings, starting and
  stopping a recording, and collecting the resulting REC file.
- Removed duplicated collection guidance, incomplete raw commands, and advanced
  SDK/REC details that obscured the primary onboarding paths.
- Consolidated advanced and contributor material behind focused documentation
  links without changing runtime behavior or compatibility claims.

## 0.4.0 — 2026-07-29

### Fixed

- Restored executable permissions on the expected Gradle launcher after safe
  ZIP extraction so a freshly provisioned decoder toolchain can build.
- Removed the SDK-tooling import cycle that could prevent `doctor` from loading
  REC and schema status together.

### Documentation

- Documented device-scoped Loop Gen 2 evidence for advertised recording types
  and activity-sample, daily-summary, and skin-temperature BPB retrieval and
  decoding.
- Recorded `/DEVICE.BPB` version evidence for the tested Loop Gen 2 and Verity
  Sense devices.
- Clarified that advertised types are not recording evidence, raw BPB retrieval
  is not decoding evidence, and blocked cleanup candidates do not constitute an
  eligible cleanup dry-run.
- Added BlueZ disconnect-timeout diagnostics for bounded reconnect failures.
- Split implemented single-file REC decoder tracking from deferred protected
  and batch decoding specifications, and aligned protected-evidence tracking
  with its current test and audit foundations.
- Moved release preparation to `dev`; release branches now remove only
  development controls, and TestPyPI candidates require a merged `main` tree
  with consistent release metadata.

### Added

- Added official-schema BPB decoding provenance, bounded/symlink-safe input
  handling, owner-private atomic JSON output, stable failure codes, and
  all-registered-schema local SDK contracts.
- Added passive-manifest BPB decoding and opt-in `passive collect --decode`,
  including payload-date validation and additive version-2 decode evidence.
- Added independent generated-schema status, verification, and activation,
  plus format-3 cache manifests that remain verifiable after SDK-source
  removal.
- Added `sdk remove --retain-schemas` for verified format-3 caches.
- Added immutable Linux x86_64/aarch64 REC-decoder toolchain descriptors,
  architecture alias normalization, descriptor-bound offline cache reuse, and
  actionable platform mismatch reporting.
- SDK removal now accepts repeated exact commit SHAs or all revisions, supports
  deterministic dry runs and bulk confirmation, and can explicitly include
  corresponding decoder runtimes/workspaces while retaining the shared JDK.
- Decoder builds now copy the pinned SDK's exact licence into the local runtime
  as attribution-only material and bind its SHA-256 and SDK commit in the
  manifest. The attribution file and compiled decoder remain excluded from
  PyPI distributions.

### Changed

- `doctor` now reports a non-fatal active SDK/decoder commit mismatch and
  suggests rebuilding the decoder without changing decoder availability.
- Simplified Polar BLE SDK licence consent to one interactive `y/N` install
  confirmation on every install/download invocation, with `-y`/`--yes` for
  unattended use. Removed persisted content-bound acceptance and generated-cache
  licence gates; decoder-local attribution is never treated as acceptance.
- Decomposed REC decoding into cohesive model, sidecar process, protocol
  validation, and publication modules, and split the JVM template into command,
  SDK parsing, payload adaptation, JSON protocol, and publication modules
  without changing the public API.

## 0.3.2 — 2026-07-27

### Fixed

- Pairing now releases its temporary BlueZ verification connection before
  returning, so follow-up async device sessions do not require a handoff.
- Pairing combines live scan observations with an explicit existing-bond
  fallback for direct connection verification.

### Changed

- Pairing now reports whether the device is ready for other actions.

## 0.3.1 — 2026-07-27

### Changed

- Pairing failures caused by BlueZ connection-attempt failures now include
  bounded retry and troubleshooting guidance.
- Discovery now excludes cached BlueZ device records and reports only devices
  observed during the active scan.
- Documented controlled Linux aarch64/BlueZ validation of Polar Loop Gen 2
  discovery, durable pairing and bonding, and FTU profile application.

## 0.3.0 — 2026-07-27

### Added

- Added high-level recording capability, settings, status, start, stop,
  trigger, disk-space, and exact raw-fetch APIs and CLI operations.
- Added complete passive PFTP sync collection, guarded delete-after-collect,
  and date/domain-bounded cleanup with local-only dry-run.
- Added stable typed collection/deletion statuses and immutable public
  collection results for raw and passive BLE operations.

### Changed

- Consolidated streaming local-file SHA-256 verification across raw and passive
  stores while retaining their separate eligibility and audit rules.
- Preserved deletion-attempt audit records while propagating BLE transport
  failures.
- Defined Polar Loop Gen 2 and Polar Verity Sense as the currently supported
  devices, limited by the documented compatibility matrix.
- Split completed core BLE requirements into SPEC-003, optional decoder
  expansion into SPEC-004, and protected compatibility certification into
  SPEC-005.

### Compatibility

- Collection/listing result collections now use tuples rather than mutable
  lists. Status fields use `StrEnum` models while retaining their existing
  string comparison and JSON representations.

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
