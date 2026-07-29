# Releasing

1. On `dev`, update the version in `pyproject.toml`, date the release heading
   in `CHANGELOG.md`, replace `RELEASE_NOTES.md` with the customer-facing
   release summary, and finish every product and documentation change. Commit
   and push the release-ready `dev` tip.
2. On that exact `dev` commit, run formatting, linting, the supported-Python
   test matrix, SDK-free unit and contract tests, and licensed SDK contracts.
3. Create `release/<version>` from the verified `origin/dev` tip. Delete
   `AGENTS.md` and `specs/` in one release-tree commit. Those deletions must be
   the only changes relative to `origin/dev`; never finish product or metadata
   work on the release branch.
4. Build and validate both distributions from the release branch:

   ```bash
   python -m build
   python -m twine check --strict dist/*
   python scripts/release_audit.py
   python -m pytest -q tests/packaging/test_artifacts.py
   ```

5. List and inspect every wheel and source-distribution member. Confirm that no
   SDK source, schema source, generated module, descriptor, `.REC`, `.BPB`,
   capture, inventory, profile, credential, decoder runtime, or hardware log is
   present. Confirm the exact decoder-template allowlist is present.
6. Install the wheel in a clean environment and run:

   ```bash
   python -c "import polar_ble_tools"
   polar-ble --version
   polar-ble --help
   polar-ble rec --help
   polar-ble rec status
   polar-ble sdk decoder --help
   polar-ble doctor
   ```

7. On a private Linux/BlueZ host, run the live single-device matrix. Confirm
   pairing, FTU, PMD, PFTP and raw retrieval; passive BPB retrieval and decoding;
   and cleanup in dry-run mode. Require at least one verified cleanup candidate
   to report `dry_run`; a blocked-only result validates the guard but not an
   eligible cleanup dry-run. Record the tested commit SHA, device model,
   advertised types, independently proven start/stop types, retrieved passive
   domains, decoded passive domains, cleanup counters, and results in a private
   release checklist. Do not commit device data, profiles, inventories, SDK
   caches, or hardware logs.
8. Merge the release pull request into `main`. From the exact merged `main`
   commit, manually dispatch the TestPyPI candidate workflow; it rejects other
   branches, development-only paths, and inconsistent release metadata.
   Install the candidate and verify all CLI groups.
9. Create the annotated release tag on that same `main` commit only after the
   candidate and manual hardware checks pass.
10. Publish to PyPI through trusted publishing and the manually approved `pypi`
    environment.
11. Create the GitHub release from `RELEASE_NOTES.md`, including artifact
    SHA-256 values and only compatibility claims backed by local evidence.

Never upload SDK source, recordings, compiled decoder output, or generated SDK
data as a CI artifact or public cache.
Production publication uses short-lived trusted-publishing credentials rather
than repository API tokens.
