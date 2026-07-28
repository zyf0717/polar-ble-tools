# Implementation plan

## Phase 1 — schema lifecycle

1. Emit generated-schema manifest format 3 with SDK source content provenance.
2. Introduce an atomic independent active-schema pointer and status model.
3. Verify format-3 caches without reading retained SDK source.
4. Preserve source-bound verification for legacy format-2 caches.
5. Add schema status, verification, activation, and source-only removal APIs
   and CLI commands.

## Phase 2 — decoder hardening

1. Add bounded regular-file reads and stable failure classification.
2. Bind every result to active schema commit, manifest version, and descriptor
   digest.
3. Publish owner-private schema-faithful JSON atomically under safe roots.
4. Keep unsupported paths non-fatal and reject corrupt evidence.

## Phase 3 — passive integration

1. Decode persisted passive manifests through a reusable local-only API.
2. Derive and cross-check cleanup-relevant payload dates.
3. Append version-2 passive evidence rows without modifying raw files.
4. Add opt-in post-collection CLI decoding and combined collection/decoding
   results.

## Phase 4 — evidence and documentation

1. Add synthetic lifecycle, safety, integration, and failure-path tests.
2. Add official-schema parse/serialize contracts for all registered schemas.
3. Run scoped private-fixture contracts when local fixtures are configured.
4. Audit the diff and distributions for restricted artifacts.
