# SPEC-009: Bleak-first operations and cross-platform readiness

**Status:** Proposed
**Milestone:** `0.5.x`
**Depends on:** SPEC-003
**Coordinates with:** SPEC-005

## Scope

SPEC-009 evaluates and migrates the package's BLE lifecycle toward a
Bleak-first, platform-neutral design:

- structured discovery and deterministic authorized-device selection;
- native Bleak device resolution before connection;
- device preparation or pairing where a supported workflow requires it;
- bounded service-readiness probing and managed connection ownership;
- disconnect, reconnect, cancellation, timeout, and failure cleanup;
- shared orchestration for PMD, PFTP, raw, passive, and FTU workflows;
- parallel device-specific FTU paths that keep Loop physical setup isolated
  from Verity runtime-time and wear-location setup;
- platform-neutral identifiers, public models, commands, and inventories;
- automated portability contracts for Linux, macOS, and Windows;
- controlled Linux hardware validation for the currently supported devices.

The experiments compare package outcomes, not implementation parity.
Successful Bleak-only operation does not need to reproduce `bluetoothctl`
commands or Linux `Paired`, `Bonded`, and `Trusted` reporting.

## Completion outcome

Every lifecycle operation receives one reviewed verdict:

1. **Bleak-only** when public Bleak APIs are sufficiently robust for the
   package outcome;
2. **Bleak plus OS adapter** when a required outcome cannot be achieved or
   observed through Bleak;
3. **Remove or redesign** when the existing operation is unnecessary or
   conflicts with managed ownership;
4. **Unsupported** when the outcome cannot be implemented or validated safely.

The accepted verdict matrix is an implementation gate, not an optional report.
Approved migration, public-contract replacement, validation, and documentation
belong to the `0.5.x` program.

## Documents

- [Requirements](requirements.md)
- [Experiments and decisions](experiments-and-decisions.md)
- [Public contracts](public-contracts.md)
- [Implementation plan](implementation-plan.md)
- [Validation](validation.md)
- [Governance](governance.md)
- [Tracker](tracker.md)

## Boundaries

- Breaking `0.4.x` BLE APIs, models, options, and lifecycle semantics is
  permitted for `0.5.0`; compatibility shims are not required.
- Native Bleak objects remain inside the BLE backend and are never persisted.
- An OS-specific adapter is permitted only for a demonstrated package need;
  it does not own PMD, PFTP, collection, storage, or decoding behavior.
- Raw REC and passive BPB retrieval remain independent of SDK tooling.
- Guarded deletion, atomic storage, audit, and decoder boundaries do not
  change.
- Linux hardware evidence preserves supported user outcomes, not the existing
  BlueZ implementation.
- macOS and Windows automation proves architectural portability only. Public
  platform support requires later physical-device evidence through SPEC-005.
- Device identifiers, inventories, captures, and hardware logs remain private.
