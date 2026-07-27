# AGENTS.md

## Scope

* Keep this repository focused on BLE tooling: transport, PMD/PFTP clients, device workflows, local retrieval and storage, decoding facades, and explicit SDK tooling.
* Do not add fleet orchestration, cloud synchronization, study workflows, dashboards, or application-level scheduling.
* Treat `docs/architecture.md`, `docs/development.md`, and `docs/compatibility.md` as the source of truth.

## Non-negotiable boundaries

* Preserve separation between BLE transport, protocol clients, device operations, collection, storage, decoding, and SDK tooling.
* Imports and property access must not use the network, access BLE, download files, generate code, or mutate device state. Such work must require an explicit function or command.
* Raw `.REC` and `.BPB` retrieval must remain independent of the Polar BLE SDK.
* Generate schemas through the existing SDK tooling; do not copy or manually translate upstream SDK schemas or implementations.
* Keep REC decoding behind the optional, verified local JVM sidecar. Schema activation and decoder activation must remain independent.
* Never commit, package, cache publicly, or upload SDK source or archives, `.proto` files, generated `_pb2.py` modules, descriptor sets, generated SDK caches, decoder runtimes, recordings, captures, device inventories, profiles, credentials, identifiers, or hardware logs.
* Preserve guarded cleanup: exact device paths, inactive-recording checks where applicable, verified local size and SHA-256, dry-run support, and deterministic audit logs.
* Use atomic writes and constrain stored paths to configured roots.
* Do not broaden device or protocol compatibility claims without reproducible evidence.

## Development workflow

```bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev,sdk]"
```

* Make the smallest coherent change and follow existing package boundaries.
* Add or update focused unit or contract tests for changed behaviour.
* Update public documentation and `CHANGELOG.md` when behaviour visible to users changes.
* Hardware and SDK contract tests are opt-in. A skipped test is not evidence that the behaviour passed.
* Do not run live device mutations unless explicitly authorized against the private device inventory.

## Release branches and pull requests

* When creating a release branch or pull request, keep `specs/` and `AGENTS.md`
  out of scope: do not stage, commit, or include changes to either in the
  release diff.

## Required checks

```bash
ruff check .
ruff format --check .
pytest -q tests/unit tests/contracts
python scripts/release_audit.py
```

For packaging changes, also run:

```bash
python -m build
python -m twine check --strict dist/*
python -m pytest -q tests/packaging/test_artifacts.py
```

For SDK or REC-decoder changes, run the applicable licensed local contract suite and verify that no upstream, generated, or private artefacts appear in the diff or built distributions.

Before finishing, review the complete diff and report which checks were run, which were not run, and why.
