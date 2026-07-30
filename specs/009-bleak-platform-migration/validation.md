# Validation

## Automated contracts

Use injected scanner, client, platform, and optional OS-adapter boundaries to
validate:

- structured advertisement mapping, filtering, deduplication, and timeout;
- opaque Linux MAC, macOS UUID, and representative Windows identifiers;
- explicit authorization before preparation or other device mutation;
- native `BLEDevice` resolution and client construction without an implicit
  string-address scan;
- already-ready, fresh-preparation, and not-required outcomes;
- bounded readiness probing and required PMD/PFTP service checks;
- exactly one connection owner per workflow;
- cleanup after success, backend failure, timeout, and cancellation in every
  lifecycle phase;
- disconnect followed by a later managed reconnect;
- deterministic same-device serialization and bounded independent-device
  coordination;
- phase-preserving errors and redacted diagnostics;
- no BLE, network, download, generation, or mutation during import or property
  access;
- stable JSON and immutable public result models;
- removal of obsolete Linux-only paths selected by the decision matrix.

Run the full supported Python matrix on Linux. Add macOS and Windows jobs for
the minimum and latest supported Python versions, covering package import,
platform selection, CLI construction, injected lifecycle contracts, build, and
wheel smoke tests. These jobs require no BLE hardware and prove no physical
compatibility.

Test the minimum declared Bleak version and newest allowed minor version.
Dependency-range changes are part of the accepted experiment result.

## Controlled Linux hardware

Use only explicitly authorized private inventory entries. Do not publish
identifiers, captures, payloads, profiles, or raw logs.

On Polar Loop Gen 2 and Polar Verity Sense, validate:

1. live structured discovery and deterministic target selection;
2. an already prepared device;
3. fresh preparation when separately authorized;
4. a bounded service-ready probe ending disconnected;
5. representative read-only PMD and PFTP operations;
6. managed disconnect and reconnect with a new client;
7. reconnect from a new process when preparation persistence is required;
8. bounded timeout/failure cleanup and a later successful recovery.
9. device-family FTU dispatch: Loop physical/user setup remains isolated, while
   Verity sets runtime system/local time and wear location with independent
   read-back.

Fresh preparation remains incomplete when no authorized unprepared state is
available. A skipped hardware case is not evidence.

The `0.4.x` path supplies a diagnostic baseline for supported user outcomes.
The `0.5.x` path need not reproduce BlueZ flags, command output, intermediate
states, or timing.

## Acceptance gates

Before migration:

- every decision-matrix row has evidence, verdict, limitation, and reviewer;
- Bleak-only and OS-adapter responsibilities form one coherent ownership model;
- the selected Bleak version range is recorded;
- no operation depends on a compatibility fallback.

Before `0.5.0` release:

```bash
ruff check .
ruff format --check .
pytest -q tests/unit tests/contracts
python scripts/release_audit.py
python -m build
python -m twine check --strict dist/*
python -m pytest -q tests/packaging/test_artifacts.py
```

Also require passing cross-platform CI, exact-commit Linux hardware evidence
for both supported devices, clean-wheel CLI smoke tests, complete public
documentation, and a complete diff review.

## Platform claims

macOS and Windows automation demonstrates import, packaging, and backend
contract portability only. Public macOS or Windows 11 compatibility requires
controlled physical-device evidence under SPEC-005. Until then, failures on
those platforms are unvalidated behavior rather than regressions against a
support claim.
