# SPEC-006: Protected REC decoding

**Status:** Deferred. Resume only after the pinned SDK security strategy,
protected fixtures, private handling, and evidence review are approved under
[SPEC-005](../005-protected-compatibility/README.md).

[The pending protocol](protected-protocol.md) is the sole definition of
FR-027–032/062. It extends the implemented
[v1 decoder](../../docs/rec-decoding.md#output-protocol-v1); no current protected
API or compatibility claim exists.

Acceptance requires synthetic v1/v2 negotiation, malformed/duplicate-key/UTF-8/
size rejection, source exclusivity/permissions, timeout/cancellation process
cleanup, and secret canaries absent from every diagnostic/persistence surface.
Private fixtures must prove each enabled SDK security strategy, official-parser
invocation, decoded semantics, and source/output digests. No SDK patches,
project-authored REC parsing/decryption, or public restricted-data retention.
Apply the shared [gates](../README.md#shared-gates).
