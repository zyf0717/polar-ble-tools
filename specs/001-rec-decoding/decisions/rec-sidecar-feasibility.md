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
- The pinned SDK is distributed as an Android library and its own build declares Android Gradle Plugin `8.7.3`,
  Kotlin `2.3.20`, Gradle wrapper `9.4.1`, Java 21 source/target compatibility, and Android `compileSdk 35`
  (minimum SDK 26). This describes the vendor build, not a demonstrated runtime requirement of the decoder.
- The decoder's static source dependency closure contains 48 Kotlin files and no `android.*` runtime imports.
  The only Android-related references are the compile-time `androidx.annotation.VisibleForTesting` annotation in
  `BlePMDClient` and `PmdTimeStampUtils`. The closure otherwise uses JDK APIs and `kotlinx-coroutines-core`.
- **Preferred candidate: pure JVM.** Compile the selected SDK source files directly from the user's cached
  checkout into the same Kotlin/JVM module as the project-owned adapter. This preserves Kotlin `internal`
  access without copying or modifying SDK source. The expected dependencies are JDK 21, Kotlin Gradle plugin
  `2.3.20`, `kotlinx-coroutines-core:1.10.2`, and `androidx.annotation:annotation:1.6.0`; no Android SDK or
  runtime is currently indicated.
- A headless Android/JVM adapter remains a fallback only if the JVM spike exposes a compile-time or runtime
  dependency not visible in the static analysis.

## Required validation before approval

1. On a machine with JDK 21, create an external Kotlin/JVM adapter workspace that compiles the selected SDK
   source files in the same module as the project-owned adapter, without changing the cached SDK source.
2. Confirm the exact source set and dependency lockfile required to invoke the internal decoder without copying
   or translating vendor implementation code.
3. Decode one locally owned, non-redistributed `.REC` sample and capture the available record categories.
4. Confirm the adapter can emit deterministic protocol-v1 JSONL and that no SDK sources, classes, AARs, or
   sample data are placed in a distributable project artifact.
5. Record the exact command, runtime dependencies, access mechanism, supported recording variants, and
   licence implications here before adding production adapter, build, or lifecycle code.

## Current blockers

- No JDK or Java runtime is installed in the implementation environment.
- No locally owned `.REC` sample is available for the required end-to-end decode.

The Phase 0 gate in [the overview](../overview.md) therefore remains closed. The repository may add no
production decoder adapter, build, lifecycle, or runtime implementation until the validation above produces
a reproducible supported path.
