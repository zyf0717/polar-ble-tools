# SPEC-003: Extended offline BLE operations and maintainability

**Status:** Proposed
**Milestone:** Ongoing development; integrate incrementally
**Repository:** `zyf0717/polar-ble-tools`
**Baseline:** current branch head
**Suggested branch:** `feat/spec-003-extended-operations`
**Date:** 2026-07-27

## Contents

- [Functional requirements](requirements.md)
- [Raw and passive operation contracts](operation-contracts.md)
- [REC sidecar and batch protocol](rec-protocol.md)
- [Models, errors, and workflow semantics](models-and-errors.md)
- [Public contracts](public-contracts.md)
- [Implementation plan](implementation-plan.md)
- [Validation and documentation](validation.md)
- [Execution rules and completion](governance.md)

## Context

This specification continues development after the `0.2.x` SDK-backed REC
sidecar work. It defines incremental capability and maintainability work rather
than a one-time migration milestone.

## Decision summary

Continue expanding `polar-ble-tools` as the maintained public implementation by:

1. exposing the existing PMD offline-recording controls through stable CLI and Python APIs;
2. adding guarded passive-file deletion and `delete-after-collect`;
3. extending the SDK-backed REC decoder to Linux aarch64, protected recordings, and batch decoding;
4. validating Loop Gen 2 and Verity Sense behavior from controlled evidence;
5. refactoring affected subsystems so the new behavior reduces duplication, clarifies ownership, and remains maintainable.

The implementation must preserve the current architecture:

- BLE, PMD, PFTP, collection, storage, verification, and orchestration remain project-owned Python;
- protobuf schemas and generated bindings remain optional local cache material,
  generated only from separately obtained and licensed SDK schema inputs;
- structured REC decoding remains an optional, locally built SDK sidecar;
- no Polar SDK source, generated SDK artifact, decoder binary, private fixture,
  secret, or device payload enters Git history, distributions, GitHub Actions
  artifacts, CI or uploaded dependency caches, container/OCI image layers,
  Gradle build scans, test reports, coverage bundles, crash dumps, debug logs,
  SBOM/provenance bundles, retained temporary CI archives, Git LFS,
  release-candidate bundles, or release assets.

Do not add a pure-Python translation of the vendor REC decoder.

## Goals

1. Continue developing the offline BLE workflow surface without coupling work
   to a one-time migration target.
2. Make offline-recording control usable without navigating internal service objects.
3. Make passive deletion as guarded and auditable as raw REC deletion.
4. Allow the REC sidecar to build and run on Raspberry Pi-class Linux aarch64 hubs.
5. Support batch REC decoding while retaining raw REC files as authoritative artifacts.
6. Support secret-protected REC decoding without exposing secrets in process arguments or logs.
7. Produce an evidence-backed compatibility matrix for Loop Gen 2 and Verity Sense.
8. Improve module boundaries, naming, result models, error handling, and testability while implementing the work.
9. Keep release-facing documentation focused only on `polar-ble-tools`, its capabilities, and its verified limitations.

## Non-goals

- Preserving undocumented command names or output formatting.
- Adding legacy executables such as `polar-raw`, `polar-passive`, or `polar-bpb`.
- Vendoring the Polar BLE SDK or generated schemas.
- Shipping a prebuilt REC decoder, JDK, Gradle distribution, SDK class, or SDK-derived binary.
- Translating Polar’s Kotlin or Swift REC decoder into Python.
- Moving S3 sync, ETL, databases, APIs, dashboards, or fleet scheduling into this package.
- Making `devices.yaml` mandatory for general library use.
- Adding Windows, macOS, or mobile BLE support.
- Guaranteeing support for devices not validated in the compatibility matrix.

## User stories

### US-1: Recording control

As an operator, I can inspect available offline-recording types and settings, start or stop recordings, inspect active status and trigger configuration, and read device disk space through `polar-ble` or stable Python functions.

### US-2: Targeted retrieval

As an operator, I can fetch one known REC path without running a whole-device collection.

### US-3: Guarded passive cleanup

As an operator, I can delete only passive BPB files whose local copies still pass manifest, size, and SHA-256 verification.

### US-4: Collect then delete

As an operator, I can request passive collection with deletion after successful persistence, while failed or unverified files remain on-device.

### US-5: Linux aarch64 REC decoding

As a Raspberry Pi-class deployment operator, I can explicitly build and verify the optional REC sidecar on Linux aarch64 using a pinned, checksum-verified toolchain.

### US-6: Batch decoding

As a data engineer, I can decode a directory tree or a manifest of REC files and receive deterministic per-file results plus a machine-readable summary.

### US-7: Protected REC decoding

As an operator, I can decode a secret-protected recording without placing the secret in command-line arguments, environment logs, output, manifests, or error messages.

### US-8: Compatibility evidence

As a maintainer, I can determine exactly which operations are confirmed for Loop Gen 2 and Verity Sense, on which host architecture, SDK revision, and package release.

## Architectural invariants

1. Existing `0.2.x` public APIs and CLI commands remain compatible unless a defect requires a documented correction.
2. `polar_ble_tools` and `polar_ble_tools.rec` remain importable without SDK material, Java, Gradle, or a decoder.
3. Package installation and import perform no SDK download, schema generation, toolchain provisioning, decoder build, or activation.
4. Raw and passive retrieval remain usable without structured decoding.
5. `polar-ble sdk install --accept-license` continues to install and activate schemas only; it must not build the REC decoder.
6. Decoder build remains an explicit `polar-ble sdk decoder build` operation.
7. Every destructive operation requires a verified local copy and appends an audit record.
8. Dry-run operations must perform no device mutation.
9. Secrets must not appear in argv, shell commands, logs, exception text, manifests, summaries, or generated filenames.
10. Subprocess invocation must use argument arrays and never `shell=True`.
11. All cache installation and activation operations must remain transactional and preserve the last verified active state on failure.
12. Public CI must use synthetic inputs and fake sidecars; SDK contracts, private REC fixtures, and hardware validation remain protected local gates.
13. Public APIs and serialized output must use project-owned names and models, not Polar SDK class names.
14. No support claim may exceed the recorded fixture and hardware evidence.
15. Protobuf message definitions, field numbers, enum definitions, descriptor
    sets, and generated language bindings are produced locally from separately
    licensed SDK schema inputs. They must not be manually transcribed,
    reconstructed, translated, committed, packaged, or published. Project code
    may map generated messages into stable project-owned models.
16. `protoc` generation occurs only in an explicit user-initiated SDK workflow.
    Generated `_pb2.py` modules and descriptor sets remain local cache material,
    retain the applicable upstream licence, and have no hand-maintained fallback
    when generation is unavailable.
17. Protected REC decoding uses the pinned official SDK parser inside the
    optional JVM sidecar. No project-authored parser, metadata reader, payload
    parser, compression decoder, decryption implementation, or Python fallback may
    decode REC content.
18. Every locally built decoder cache entry contains the exact resolved SDK
    licence and required upstream notices, each cache-relative, SHA-256
    recorded, and verified before activation or use.
19. Real-device data, decoded participant data, device identifiers, profile
    contents, and secrets remain protected. The package is not specified for
    diagnostic, clinical, medical-device, life-supporting, or life-critical
    use.
