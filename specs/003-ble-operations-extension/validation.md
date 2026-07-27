# Validation

## Automated contracts

Validate:

- package import without SDK material, Java, Gradle, or a decoder;
- pre-session type, setting, trigger, date, domain, and raw-path validation;
- exact raw targeted fetch, atomic publication, size, digest, alias, symlink,
  and no-clobber behavior;
- bounded stop confirmation and typed timeout behavior;
- same-device serialization and cancellation-safe lock/session release;
- passive sync start/termination on success, failure, and cancellation;
- passive skip reverification and overwrite publication;
- delete-after-collect retention of unknown and latest dates;
- cleanup domain/date/path restrictions and local-only dry-run;
- exact local manifest, size, and streaming SHA-256 verification;
- immutable public result collections and stable JSON status strings;
- per-file protocol continuation and transport-failure propagation;
- append-only, deterministic, payload-free deletion audit records.

## Release gates

For the exact release candidate:

```bash
ruff check src tests
ruff format --check src tests
python -m pytest -q
python -m build
python -m twine check --strict dist/*
python scripts/release_audit.py
python -m pytest -q tests/packaging/test_artifacts.py
```

Install the built wheel into a clean environment, import the package, and run
`polar-ble --version` and `polar-ble --help`.

Private hardware smoke testing for the exact release commit follows SPEC-005
and the release procedure. It validates support claims but is not replaced by
unit tests.

## Documentation

Release-facing documentation must:

- state Polar Loop Gen 2 and Polar Verity Sense as the currently supported
  devices;
- distinguish confirmed operations from unsupported or unvalidated behavior;
- document immutable Python result collections and stable serialized values;
- explain raw/passive persistence and guarded deletion;
- keep optional decoder requirements separate from core BLE retrieval;
- retain SDK separation, privacy, and non-medical boundaries.
