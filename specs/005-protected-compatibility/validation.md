# Validation

## Implemented test foundations

The repository has opt-in probes for a primary device, selected reconnect/PMD
operations, one passive daily-summary retrieval/decode, cleanup dry-run, and an
optional two-device read-only concurrency check. These probes do not implement
the complete requirements below and a skipped probe is not evidence.

`scripts/release_audit.py` scans repository paths and history. Packaging tests
inspect wheel/sdist contents. External workflow, cache, report, container, and
release-asset inspection remains deferred.

## Deferred hardware matrix

Use controlled, disposable recordings for destructive tests. Exercise:

- discovery, pairing, trust, connect/disconnect/reconnect;
- supported PMD capabilities, settings, status, start, stop, and triggers;
- disk space, exact fetch, collection, verification, and cleanup dry-run;
- one separately approved destructive deletion where required;
- passive domains only where device behavior provides evidence;
- two-device concurrency/cancellation and controlled radio loss.

## Deferred protected fixtures

For each claimed decoder/schema category:

- bind source/output digests to an intentional contract version;
- validate fields, units, nullability, numeric and timestamp policy;
- prevent unknown SDK fields from appearing opportunistically;
- keep sources, outputs, profiles, identities, and secrets out of reports and
  uploads;
- record private retention and deletion.

## Deferred certification audit

Inspect repository state, history, workflow configuration, wheel, sdist,
artifacts, caches, container layers, reports, scans, bundles, and release assets
for prohibited SDK/private material. Project-authored decoder templates are
allowed; SDK source, generated SDK artifacts, decoder runtimes, real REC/BPB
fixtures, inventories, profiles, acceptance records, and secrets are not.

Detailed release-candidate audit gates are deferred pending maintainer approval.
