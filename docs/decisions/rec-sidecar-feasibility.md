# REC decoder sidecar feasibility

**Status:** blocked — production adapter not approved

**SDK commit:** `ccff6812c40fff1753c72385387d1877ca9b27b4` (the release pin).

## Findings

- The Android SDK's decode entry point is the internal Kotlin API
  `com.polar.androidcommunications.api.ble.model.offlinerecording.OfflineRecordingData.parseDataFromOfflineFile`.
  It accepts the complete recording bytes, a `PmdMeasurementType`, and an optional `PmdSecret`.
- File-name-to-measurement mapping is also internal:
  `OfflineRecordingUtility.mapOfflineRecordingFileNameToMeasurementType`.  The supported names include
  `ACC`, `GYRO`, `MAG`, `PPG`, `PPI`, `HR`, `TEMP`, and `SKINTEMP`, with numeric suffixes accepted.
- The entry point and its result types are not part of the SDK's public API. A sidecar must therefore prove
  that it can access this implementation without copying vendor source or mutating the cached SDK checkout.
- The pinned SDK is an Android library, not a plain JVM module. Its build declares Android Gradle Plugin
  `8.7.3`, Kotlin `2.3.20`, Gradle wrapper `9.4.1`, Java 21 source/target compatibility, and Android
  `compileSdk 35` (minimum SDK 26).
- The decoder's direct package mostly uses JVM APIs, but it depends on SDK PMD classes whose build is produced
  by the Android toolchain. A pure-JVM mode is therefore unproven; the current candidate is a headless
  Android/JVM adapter.

## Required validation before approval

1. On a machine with JDK 21, Android SDK platform 35, and the SDK's Gradle wrapper, create an external,
   project-owned adapter workspace without changing the cached SDK source.
2. Establish a reproducible way to invoke the internal decoder (or identify a supported public replacement)
   without copying or translating vendor implementation code.
3. Decode one locally owned, non-redistributed `.REC` sample and capture the available record categories.
4. Confirm the adapter can emit deterministic protocol-v1 JSONL and that no SDK sources, classes, AARs, or
   sample data are placed in a distributable project artifact.
5. Record the exact command, runtime dependencies, access mechanism, supported recording variants, and
   licence implications here before adding production adapter, build, or lifecycle code.

## Current blockers

- No JDK or Java runtime is installed in the implementation environment.
- No Android SDK/toolchain is installed or verified.
- No locally owned `.REC` sample is available for the required end-to-end decode.

The Phase 0 gate in `specs/001-rec-decoding.md` therefore remains closed. The repository may add no
production decoder adapter, build, lifecycle, or runtime implementation until the validation above produces
a reproducible supported path.
