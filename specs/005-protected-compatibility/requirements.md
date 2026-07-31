# Functional requirements

## Device compatibility

**FR-040** — Maintain an evidence-backed matrix for Polar Loop Gen 2 and Polar
Verity Sense.

**FR-041** — Loop Gen 2 validation covers discovery, pairing, trust, connect,
disconnect, reconnect, recording capabilities/settings/status/start/stop,
supported triggers, disk space, raw list/fetch/collect/cleanup dry-run, passive
list/collect/cleanup dry-run, one approved destructive cleanup, and every
schema/decoder category publicly claimed.

**FR-042** — Verity Sense validation covers recording capabilities,
settings/status/start/stop, supported triggers, raw retrieval and guarded
deletion, and each claimed measurement category. Passive activity, sleep,
wellness, or related domains are not claimed unless separately advertised and
validated.

**FR-043** — A two-physical-device test proves same-device serialization,
bounded independent-device concurrency, deterministic results, and
cancellation/failure release of locks, limiters, notifications, and sessions.

**FR-044** — Controlled reconnect and radio-loss exercises record actual
recovery limits without weakening timeouts or adding unsafe automatic retries.

**FR-045** — Public compatibility claims derive only from controlled fixture or
hardware evidence for the exact package commit/version.

**FR-091** — Before any macOS or Windows support claim, add host-native
automated import, packaging, CLI, lifecycle, and cleanup workflows, then run
the applicable controlled hardware matrix. Platform-neutral APIs and injected
identifier shapes are not substitute evidence.

## Maintainability and protected data

**FR-058** — Every certification cycle reviews module ownership, duplicate
logic, dependency direction, public/internal surface, typed errors/models, test
coupling, and documentation drift for the touched workstreams.

**FR-064** — SDK-derived and private material never enters Git history, public
CI artifacts/caches, container layers, build scans, test/coverage/crash
reports, SBOM/provenance bundles, retained temporary archives, Git LFS,
release-candidate bundles, distributions, or release assets.

**FR-065** — Real-device fixtures are consented, disposable or approved,
synthetic where possible, purpose-limited, access-controlled, and subject to a
documented retention/deletion policy. Evidence redacts participant/device
identity, profiles, payloads, decoded data, secrets, and exact private paths.
Documentation retains privacy responsibility and non-medical positioning.
