# REC decoder sidecar feasibility

**Status:** pure-JVM decoder validated against a local PPI recording; adapter protocol pending

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

## Pure-JVM spike validation

The project-owned setup script, `scripts/setup_rec_jvm_spike.sh`, provisioned the following checksum-verified
local toolchain without downloading or modifying the SDK checkout:

- Temurin JDK `21.0.12+8`;
- Gradle `9.4.1`;
- Kotlin Gradle plugin `2.3.20`;
- `kotlinx-coroutines-core:1.10.2` and `androidx.annotation:annotation:1.6.0`.

An external Kotlin/JVM project compiled the selected SDK dependency closure in the same module as a
project-owned smoke adapter. The source set includes the offline-recording parser, the complete PMD root
package, PMD model classes, and their required BLE/common support classes. No Android SDK, Android runtime, or
Android Gradle Plugin was present.

The smoke adapter executed successfully. It invoked `BlePMDClient.parseDeltaFramesAll` and
`OfflineRecordingData.parseDataFromOfflineFile`; the latter correctly rejected an empty input through the
official parser. The vendor sources emit Kotlin 2.3 warnings, so the spike must not use warnings-as-errors.

A locally owned, repository-tracked Loop Gen 2 `PPI0.REC` fixture was then passed directly to the pinned SDK
parser without copying it into this repository or the spike workspace. The parser returned `PpiData` with seven
samples on two independent runs; the results were equal and match the fixture's existing expected count. This
validates the `PPI` record category for an unencrypted recording.

This validates the pure-JVM build and class-loading path. It does **not** validate decoding semantics, record
categories beyond PPI, JSONL output, encrypted recordings, or deterministic output beyond the validated PPI
fixture.

## Required validation before approval

1. Capture the exact source set and dependency lockfile in the isolated build workspace.
2. Confirm the adapter can emit deterministic protocol-v1 JSONL and that no SDK sources, classes, AARs, or
   sample data are placed in a distributable project artifact.
3. Record the exact command, runtime dependencies, access mechanism, supported recording variants, and
   licence implications here before adding production adapter, build, or lifecycle code.

## Current blockers

- No JSONL adapter has yet exercised the official parser against a non-empty recording.

The Phase 0 gate in [the overview](../overview.md) therefore remains closed. The repository may add no
production decoder adapter, build, lifecycle, or runtime implementation until the validation above produces
a reproducible supported path.
