# SPEC-001-REC-DECODING: Optional SDK-backed `.REC` decoder sidecar

**Status:** In progress — PPI experimental path implemented
**Target:** `polar-ble-tools` 0.2.0
**Repository baseline:** `main` at `6d087f8249cfb658f9752c96b1da74e566e8b02a`
**Implementation branch:** `feat/rec-decoder-sidecar`

## 1. Decision summary

Add structured `.REC` decoding as an **optional local sidecar** built by the user from a separately obtained Polar BLE SDK checkout.

`polar-ble-tools` will:

- continue to retrieve and preserve raw `.REC` files without schemas or SDK tooling;
- expose a stable project-owned Python API and CLI for decoding;
- build, verify, activate, invoke, and remove a decoder executable in the user data directory;
- communicate with the executable through a versioned, streaming JSONL protocol;
- never distribute the Polar SDK, SDK-derived source, generated SDK artifacts, or compiled decoder binaries.

The sidecar will:

- be built only after an explicit user command;
- call the official decoder implementation from the user's local SDK checkout;
- return project-owned normalized output rather than Kotlin, Swift, or SDK object types;
- run out of process so vendor dependencies cannot leak into the Python runtime.

## 2. Goals

1. Decode local `.REC` files without manually porting the official Kotlin or Swift decoder.
2. Preserve the existing licensing and packaging boundary.
3. Keep raw retrieval independent from decoding availability.
4. Provide deterministic, machine-readable output suitable for downstream storage and analysis.
5. Fail clearly when the SDK, build toolchain, compatible decoder, or verified sidecar is unavailable.
6. Make almost all Python behavior testable without downloading the Polar SDK or requiring hardware.

## 3. Non-goals

- Shipping a decoder binary in wheels, sdists, GitHub releases, or CI artifacts.
- Shipping or copying Polar SDK source, generated schemas, or SDK-derived files.
- Translating the official decoder into Python.
- Automatically building a decoder during package installation, import, SDK installation, or schema generation.
- Decoding files directly during BLE collection.
- Supporting CSV, Parquet, databases, or analytics transformations in the first release.
- Guaranteeing support for every Polar device or `.REC` variant.
- Running unverified decoder executables by default.
- Adding cloud decoding or remote execution.

## 4. Architectural invariants

These requirements are mandatory:

1. `polar_ble_tools.rec` must import successfully on a clean installation with no SDK, JDK, Gradle, Android SDK, or decoder.
2. `polar-ble raw` behavior must remain unchanged and must never invoke the decoder.
3. `polar-ble sdk install --accept-license` must not build the decoder.
4. Package installation and module import must perform no download, generation, build, or activation.
5. Decoder build output must remain under the user-owned cache/data root.
6. The Python package must not import or expose SDK classes.
7. Runtime invocation must use argument arrays, never `shell=True`.
8. Destination files must be written atomically and must not be overwritten unless explicitly requested.
9. A decoder is usable only when its manifest, executable digest, protocol version, and verification state are valid.
10. Public CI must not download the Polar SDK or publish locally built decoder artifacts.

## 5. High-level architecture

```text
polar-ble-tools
├── raw retrieval and storage                 existing; unchanged
├── polar_ble_tools.rec                       stable public facade
│   ├── status and capability detection
│   ├── decode orchestration
│   ├── project-owned result models
│   └── protocol validation
├── polar_ble_tools.sdk_tools.decoder         local lifecycle tooling
│   ├── feasibility/discovery
│   ├── build workspace generation
│   ├── build and activation
│   ├── manifest verification
│   └── removal
└── local decoder executable                  never distributed
    └── official SDK decoder implementation
```

Recommended package layout:

```text
src/polar_ble_tools/
├── rec/
│   ├── __init__.py
│   ├── api.py
│   ├── errors.py
│   ├── models.py
│   ├── protocol.py
│   └── runtime.py
├── commands/
│   └── rec.py
└── sdk_tools/
    ├── decoder/
    │   ├── __init__.py
    │   ├── builder.py
    │   ├── discovery.py
    │   ├── manifest.py
    │   ├── verifier.py
    │   └── workspace.py
    └── decoder_project/
        ├── project-owned build templates
        └── project-owned Kotlin adapter source
```

The adapter source may be distributed because it is project-authored. It must not contain copied SDK implementation code.

## 6. Feasibility gate

Do not begin the production adapter until a focused feasibility spike confirms the official SDK integration path.

Create:

```text
decisions/rec-sidecar-feasibility.md
```

The spike must identify:

- the exact supported Polar SDK commit;
- the official `.REC` decode entry point and required modules;
- whether the decoder can run on a plain JVM;
- whether Android SDK/runtime classes are required;
- the minimum JDK, Gradle, Kotlin, and optional Android toolchain versions;
- whether the decoder can be invoked without modifying vendor source;
- the decoded record categories available from at least one locally owned sample;
- any SDK API instability or internal/private API use;
- build and runtime licence implications requiring user action;
- the recommended build mode.

Permitted build modes, in priority order:

1. **Pure JVM adapter:** preferred when the required SDK modules compile without Android runtime dependencies.
2. **Headless Android/JVM adapter:** allowed when the official decoder requires Android build tooling but can execute locally without a device or emulator.

Stop and report instead of implementing the feature if the official implementation requires:

- copying substantial vendor source into this repository;
- manually translating the decoder;
- patching the SDK in a way that cannot be generated reproducibly outside the repository;
- redistributing restricted binaries;
- unsupported runtime behavior that cannot be verified.
