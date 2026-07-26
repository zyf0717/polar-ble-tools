# Implementation plan

## Phase 1 — recording-control API, CLI, and boundary refactor

1. Review ownership across `commands`, `api`, `collection`, `device`, and `polar` before adding commands.
2. Refactor reusable session/workflow plumbing where it is currently duplicated.
3. Add workflow functions around existing `OfflineRecordingControlClient` and `PftpClient`.
4. Add pre-session normalization for measurement types, settings, triggers,
   secrets, and exact raw fetch paths.
5. Extend `commands/raw.py` with parsing and presentation only.
6. Add immutable recording-control, disk-space, and targeted-fetch result
   models.
7. Centralize atomic no-clobber publication and streaming SHA-256 through the
   existing storage utility boundary.
8. Remove obsolete or duplicate raw command helpers within the touched scope.
9. Update CLI and Python API documentation.
10. Add SDK-free unit tests through stable workflow boundaries.

Expected files:

```text
src/polar_ble_tools/api.py
src/polar_ble_tools/collection.py
src/polar_ble_tools/commands/raw.py
src/polar_ble_tools/commands/raw_options.py        # add only if justified
src/polar_ble_tools/polar/offline.py
src/polar_ble_tools/polar/pftp.py
src/polar_ble_tools/__init__.py
tests/unit/test_api.py
tests/unit/test_raw_cli.py
tests/unit/test_offline.py
tests/unit/test_pftp.py
docs/cli-reference.md
docs/python-api.md
```

## Phase 2 — passive deletion safety and storage refactor

1. Compare raw and passive persistence/deletion invariants and extract only genuinely shared storage utilities.
2. Add a complete passive sync-session boundary.
3. Add explicit `skip`/`overwrite` existing-file policy while preserving
   `skip` as the compatibility default.
4. Extend passive storage with append-only schema-versioned manifests,
   verified latest-row cleanup selection, and deletion audit.
5. Refactor collector result construction to keep listing, collection,
   verification, retention, and deletion outcomes explicit.
6. Add latest-observed-date retention for `delete_after_collect`.
7. Add `delete_after_collect` and `cleanup_passive_files`.
8. Add CLI options and strict date/domain validation.
9. Test local-only dry-run and destructive paths through stable
   collector/client contracts.

Expected files:

```text
src/polar_ble_tools/collection.py
src/polar_ble_tools/commands/passive.py
src/polar_ble_tools/passive_data/collector.py
src/polar_ble_tools/passive_data/storage.py
src/polar_ble_tools/polar/passive.py
tests/unit/test_passive_cli.py
tests/unit/test_passive_collector.py
tests/unit/test_passive_storage.py
tests/unit/test_passive.py
```

## Phase 3 — ARM64 sidecar and toolchain model refactor

1. Refactor toolchain constants into architecture-indexed immutable descriptors.
2. Add pinned Linux ARM64 JDK provenance.
3. Normalize `amd64`/`arm64` host aliases at one boundary.
4. Generalize provisioning, manifest writing, verification, status checks, and
   remediation across descriptors.
5. Record descriptor and runtime digests in the active decoder manifest.
6. Add synthetic unit tests for both architectures.
7. Run a protected ARM64 build/self-test on Raspberry Pi OS or Ubuntu ARM64.

Expected files:

```text
src/polar_ble_tools/sdk_tools/decoder/toolchain.py
src/polar_ble_tools/sdk_tools/decoder/lifecycle.py
src/polar_ble_tools/rec/api.py
tests/unit/test_decoder_toolchain.py
tests/unit/test_decoder_lifecycle.py
tests/sdk_decoder_contract/
docs/rec-decoding.md
docs/compatibility.md
```

## Phase 4 — secret-aware sidecar protocol and invocation refactor

1. Document v1/v2 negotiation, capabilities, bounded request/status schemas,
   and stable error codes.
2. Implement redacted immutable secret models, owner-private CLI sources, and
   provider validation.
3. Implement the single-request stdin process lifecycle, bounded concurrent
   stream draining, timeout/cancellation process-group cleanup, and canary
   redaction checks.
4. Extend the project-owned Kotlin adapter.
5. Preserve protocol-v1 unencrypted operation.
6. Add fake-sidecar tests proving secrets never reach argv, environment,
   diagnostics, logs, manifests, or outputs.
7. Validate controlled encrypted fixtures privately.

Expected files:

```text
src/polar_ble_tools/rec/api.py
src/polar_ble_tools/rec/protocol.py              # add if separation improves clarity
src/polar_ble_tools/rec/models.py                # add if separation improves clarity
src/polar_ble_tools/sdk_tools/decoder_project/DecoderMain.kt
tests/unit/test_rec.py
tests/sdk_decoder_contract/test_local_rec_corpus.py
docs/rec-decoding.md
```

Do not create abstraction files that merely move a few constants without establishing a real boundary.

## Phase 5 — batch decoding and REC module decomposition

1. Decompose REC input discovery, sidecar invocation, output validation, and publication into cohesive internal boundaries.
2. Implement non-symlink deterministic input discovery and strict
   schema-versioned manifest validation.
3. Preflight every source/output mapping and no-clobber conflict before the
   first sidecar invocation.
4. Reuse single-file decode publication and validation without copying
   orchestration logic.
5. Add immutable summary/result models, relative-path serialization, and thin
   CLI commands.
6. Add unsupported-only, partial-failure, digest-mismatch, overwrite, summary
   publication, and refactor-resilience tests.
7. Add private corpus runs across all claimed categories.

Expected files:

```text
src/polar_ble_tools/rec/batch.py
src/polar_ble_tools/commands/rec.py
src/polar_ble_tools/rec/__init__.py
tests/unit/test_rec_batch.py
tests/unit/test_rec_cli.py
docs/cli-reference.md
docs/python-api.md
docs/rec-decoding.md
```

## Phase 6 — protected validation, maintenance review, and release readiness

1. Run ordinary tests, packaging audit, SDK contract tests, and private fixture contracts.
2. Run Loop Gen 2 and Verity Sense protected hardware matrices.
3. Run ARM64 decoder build and decode.
4. Run two-device concurrency and controlled radio-loss checks.
5. Perform the maintainability review from FR-058 across every touched subsystem.
6. Remove remaining avoidable duplication, responsibility leaks, stale code paths, and documentation drift.
7. Update compatibility claims strictly from recorded evidence.
8. Prepare release-ready artifacts through the existing build-once TestPyPI-to-PyPI promotion process when the maintainer chooses a release version.
9. Ensure all release-facing text describes only `polar-ble-tools`, its changes, and its supported boundaries.
