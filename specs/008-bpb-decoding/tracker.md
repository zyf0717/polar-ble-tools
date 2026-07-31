# SPEC-008 tracker

- [x] **FR-067** — Official local schema generation only.
- [x] **FR-068** — Complete schema-cache provenance.
- [x] **FR-069** — Independent format-3 activation and legacy v2 support.
- [x] **FR-070** — Retained-schema SDK-source removal.
- [x] **FR-071** — All registered schema-faithful decoders.
- [x] **FR-072** — Safe bounded I/O and atomic private publication.
- [x] **FR-073** — Stable APIs, commands, results, and failure codes.
- [x] **FR-074** — Opt-in post-collection passive decoding.
- [x] **FR-075** — Authoritative logical-date enrichment and mismatch rejection.
- [x] **FR-076** — Preserved raw and decoded evidence.
- [x] **FR-077** — Complete official-schema and scoped fixture contracts.

Completion evidence: 12 registered official bindings passed parse/serialize
round trips; five scoped local BPB fixtures passed format-3 decoding. The
configurable private-corpus test remains environment-gated by design.
