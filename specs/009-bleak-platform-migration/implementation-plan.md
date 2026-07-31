# Implementation plan

Implementation follows the reviewed evidence matrix. A phase may not infer the
next phase's verdict.

## Phase 1 — baseline and experiments

1. Capture the current Linux discovery, preparation, readiness, disconnect,
   reconnect, and supported PMD/PFTP outcomes.
2. Build injected Bleak scanner/client experiment boundaries without changing
   public defaults.
3. Run the required synthetic, version-range, and controlled Linux hardware
   experiments.
4. Complete and review every decision-matrix row.

## Phase 2 — transport and identity migration

1. Implement structured Bleak advertisement discovery.
2. Replace MAC-specific internal target handling with opaque identifiers and
   explicit authorization.
3. Resolve native `BLEDevice` objects immediately before client construction.
4. Implement typed lifecycle phases, bounded timeouts, cancellation, and
   partial-connect cleanup.
5. Add only the OS adapters approved by the matrix.

## Phase 3 — ownership and public contracts

1. Implement preparation and bounded readiness probing under one connection
   owner.
2. Route PMD, PFTP, raw, passive, and FTU commands through shared workflow
   orchestration.
3. Dispatch Loop Gen 2 and Verity Sense FTU through isolated protocol-client
   paths, including runtime time setup for Verity Sense.
4. Replace persistent connect/release behavior and remove obsolete
   `bluetoothctl` parsing, models, arguments, and entry points according to the
   accepted verdicts.
5. Publish the platform-neutral asynchronous Python and CLI contracts.

## Phase 4 — validation and `0.5.x` release

1. Run the full Linux automated matrix and packaging smoke tests.
2. Run the controlled Linux hardware matrix on both supported devices.
3. Review the complete diff for prohibited artifacts and unintended protocol,
   storage, cleanup, or decoder changes.
4. Update public architecture, configuration, API/CLI, troubleshooting,
   compatibility, changelog, and `0.5.0` release notes.
5. Defer macOS and Windows workflows and certification to SPEC-005; do not add
   platform support claims without its evidence.
