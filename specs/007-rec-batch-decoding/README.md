# SPEC-007: REC batch decoding

**Status:** Deferred; product priority and single-file certification required
**Depends on:** SPEC-004; optional protected sources require SPEC-006

## Scope

SPEC-007 owns deterministic orchestration over the package-managed single-file
decoder:

- tree and strict manifest discovery;
- complete destination preflight;
- per-file outcomes and continued execution;
- atomic versioned summaries;
- optional secure provider selection for protected sources.

It does not change REC parsing, payload adaptation, or the SDK boundary.

## Documents

- [Requirements](requirements.md)
- [Batch protocol](batch-protocol.md)
- [Models and errors](models-and-errors.md)
- [Implementation plan](implementation-plan.md)
- [Validation](validation.md)
- [Governance](governance.md)
- [Tracker](tracker.md)

## Boundaries

- Batch work remains deferred until SPEC-004 single-file adapters are certified
  and batch decoding is approved as a product priority.
- Batch orchestration delegates every decode to the verified single-file API.
- Manifests and summaries never contain inline secrets.
- Partial failures never weaken source, destination, or publication safety.
