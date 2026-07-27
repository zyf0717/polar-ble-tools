# Validation

## Hardware

Use controlled, disposable recordings for destructive tests. Exercise:

- discovery, pairing, trust, connect/disconnect/reconnect;
- supported PMD capabilities, settings, status, start, stop, and triggers;
- disk space, exact fetch, collection, verification, and cleanup dry-run;
- one separately approved destructive deletion where required;
- passive domains only where device behavior provides evidence;
- two-device concurrency/cancellation and controlled radio loss.

## Protected fixtures

For each claimed decoder/schema category:

- bind source/output digests to an intentional contract version;
- validate fields, units, nullability, numeric and timestamp policy;
- prevent unknown SDK fields from appearing opportunistically;
- keep sources, outputs, profiles, identities, and secrets out of reports and
  uploads;
- record private retention and deletion.

## Release artifact audit

Run the gates below against one full lowercase candidate commit SHA. Any gate
that cannot be inspected or produces incomplete output fails certification.

### Automated local gates

1. Require a clean tracked worktree at the candidate commit.
2. Run `python scripts/release_audit.py`; it scans current tracked paths, every
   reachable Git revision, blob secret signatures, and leaked local paths.
3. Run the required lint, format, unit, contract, and applicable licensed local
   contract suites. A skipped hardware or SDK contract is not a pass.
4. Build wheel and sdist from the candidate, run strict metadata checks, and
   run `tests/packaging/test_artifacts.py`.
5. List every distribution member and compare project-owned SDK template files
   with the exact allowlist. Reject all other SDK, generated, compiled, private,
   fixture, inventory, profile, capture, log, and credential material.
6. Install the wheel in a clean environment and run the documented import and
   CLI smoke checks.

The automated scanner is an allowlist aid, not evidence that external systems
are clean.

### Protected infrastructure gates

The reviewer inspects the candidate workflow runs, artifact inventories, cache
keys/contents, retained temporary archives, build scans, coverage/crash/test
reports, SBOM and provenance bundles, container layers, Git LFS, candidate
bundles, and draft release assets. Public jobs must not receive private
fixtures, inventories, SDK source, generated SDK artifacts, decoder runtimes,
acceptance records, or secrets.

Record for each surface: candidate SHA, inspection time, reviewer, result,
artifact identifiers and digests where applicable, and deletion/expiry state.
The record remains private. A surface that is unavailable for inspection is
`unvalidated`, not implicitly clean.

### Failure reporting and final approval

Failure reports contain only category counts and project-owned stable error
codes. Do not print matched secret text, blob contents, private paths, payloads,
device identity, or fixture identifiers. Quarantine affected artifacts,
invalidate exposed credentials, delete prohibited retained copies, and rerun
the complete audit on a new candidate.

Certification additionally requires exact-commit hardware smoke, review of
every proposed public compatibility row, and completed retention/deletion
actions. Publication approval is a separate user-owned action.
