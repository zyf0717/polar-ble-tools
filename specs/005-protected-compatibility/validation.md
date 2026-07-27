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

Inspect repository state, history, workflow configuration, wheel, sdist,
artifacts, caches, container layers, reports, scans, bundles, and release assets
for prohibited SDK/private material. Project-authored decoder templates are
allowed; SDK source, generated SDK artifacts, decoder runtimes, real REC/BPB
fixtures, inventories, profiles, acceptance records, and secrets are not.
