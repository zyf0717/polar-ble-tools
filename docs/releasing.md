# Releasing

1. Update the version in `pyproject.toml`, `CHANGELOG.md`, and release notes.
2. Run formatting, linting, the supported-Python test matrix, SDK-free unit and
   contract tests, and licensed SDK contracts.
3. Build and validate both distributions:

   ```bash
   python -m build
   python -m twine check --strict dist/*
   python scripts/release_audit.py
   python -m pytest -q tests/packaging/test_artifacts.py
   ```

4. List and inspect every wheel and source-distribution member. Confirm that no
   SDK source, schema source, generated module, descriptor, `.REC`, `.BPB`,
   capture, inventory, profile, credential, decoder runtime, or hardware log is
   present. Confirm the exact decoder-template allowlist is present.
5. Install the wheel in a clean environment and run:

   ```bash
   python -c "import polar_ble_tools"
   polar-ble --version
   polar-ble --help
   polar-ble rec --help
   polar-ble rec status
   polar-ble sdk decoder --help
   polar-ble doctor
   ```

6. On a private Linux/BlueZ host, run the live single-device matrix. Confirm
   pairing, FTU, PMD, PFTP and raw retrieval; passive BPB retrieval and decoding;
   and cleanup in dry-run mode. Record the tested commit SHA, device model, and
   results in a private release checklist. Do not commit device data, profiles,
   inventories, SDK caches, or hardware logs.
7. Publish a candidate to TestPyPI through the protected `testpypi` environment,
   install it, and verify all CLI groups.
8. Create the annotated release tag only after candidate and manual hardware checks
   pass.
9. Publish to PyPI through trusted publishing and the manually approved `pypi`
   environment.
10. Create the GitHub release using product-focused release notes and artifact
   SHA-256 values.

Never upload SDK source, recordings, compiled decoder output, or generated SDK
data as a CI artifact or public cache.
Production publication uses short-lived trusted-publishing credentials rather
than repository API tokens.
