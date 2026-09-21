# polar-ble-tools 0.6.0

`0.6.0` adds preliminary macOS and Windows support while retaining the existing
Linux/BlueZ workflows and strict local-only data boundaries.

## Platform support

- macOS/CoreBluetooth supports structured discovery, managed sessions, and the
  SDK-free workflow surface. Controlled Loop Gen 2 evidence covers readiness,
  FTU, ACC recording/retrieval, and guarded cleanup.
- Windows preparation now requests encrypted Bleak pairing with
  `protection_level=2`, even when public services are already visible, and
  verifies an ordinary reconnect before reporting readiness.
- BLE discovery and device resolution use a 30-second default across supported
  operating systems.

## SDK and REC decoding

- Pinned REC decoder toolchains now cover Linux and macOS on x86_64 and arm64,
  plus Windows x86_64.
- Windows decoder installation uses safe ZIP extraction and native Gradle and
  decoder launchers.
- SDK source hashing supports extended Windows paths beneath the default local
  cache.
- Controlled macOS arm64 and Windows x86_64 runs decoded retrieved ACC
  recordings into structured local output.

## Scope

The macOS and Windows results are preliminary device evidence, not broad
hardware certification. Batch and protected REC decoding remain unsupported.
Distributions exclude SDK source and archives, schemas, generated bindings,
decoder runtimes, recordings, captures, inventories, profiles, credentials,
identifiers, and hardware logs.
