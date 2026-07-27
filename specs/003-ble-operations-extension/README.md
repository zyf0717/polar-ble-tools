# SPEC-003: Extended offline BLE operations and maintainability

**Status:** Core implementation complete; release handoff pending
**Milestone:** Release-ready BLE recording, retrieval, and guarded cleanup
**Repository:** `zyf0717/polar-ble-tools`
**Baseline:** current branch head
**Suggested branch:** `feat/spec-003-extended-operations`
**Date:** 2026-07-27

## Contents

- [Functional requirements](requirements.md)
- [Raw and passive operation contracts](operation-contracts.md)
- [Models, errors, and workflow semantics](models-and-errors.md)
- [Public contracts](public-contracts.md)
- [Implementation plan](implementation-plan.md)
- [Validation and documentation](validation.md)
- [Execution rules and completion](governance.md)

## Context

This specification defines the core BLE recording, retrieval, and guarded
cleanup surface. Optional REC decoder expansion and protected certification are
separate follow-on programs.

## Decision summary

Continue expanding `polar-ble-tools` as the maintained public implementation by:

1. exposing the existing PMD offline-recording controls through stable CLI and Python APIs;
2. adding guarded passive-file deletion and `delete-after-collect`;
3. refactoring affected subsystems so the new behavior reduces duplication,
   clarifies ownership, and remains maintainable.

Deferred work is tracked by
[SPEC-004](../004-rec-decoder-extension/README.md) for optional REC decoder
extensions and [SPEC-005](../005-protected-compatibility/README.md) for protected
hardware and release evidence.

The core implementation must preserve the current architecture:

- BLE, PMD, PFTP, collection, storage, verification, and orchestration remain project-owned Python;
- raw and passive retrieval remain independent of optional decoders;
- destructive operations remain verified, bounded, and audited;
- device payloads and identifiers remain outside Git and public artifacts.

## Goals

1. Continue developing the offline BLE workflow surface without coupling work
   to a one-time migration target.
2. Make offline-recording control usable without navigating internal service objects.
3. Make passive deletion as guarded and auditable as raw REC deletion.
4. Improve module boundaries, naming, result models, error handling, and
   testability while implementing the work.
5. Keep release-facing documentation focused only on `polar-ble-tools`, its
   capabilities, and its verified limitations.

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

## Architectural invariants

1. Existing `0.2.x` public APIs and CLI commands remain compatible unless a defect requires a documented correction.
2. The base package remains importable without SDK material, Java, Gradle, or a decoder.
3. Package installation and import perform no network access, generation, provisioning, build, or activation.
4. Raw and passive retrieval remain usable without structured decoding.
5. Every destructive operation requires a verified local copy and appends an audit record.
6. Dry-run operations perform no device mutation.
7. Public APIs and serialized output use project-owned names and models.
8. No support claim exceeds recorded fixture and hardware evidence.
9. Real-device data, identifiers, profiles, and secrets remain protected. The
   package is not diagnostic, clinical, medical-device, life-supporting, or
   life-critical software.
