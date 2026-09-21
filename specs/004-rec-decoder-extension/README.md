# SPEC-004: Remaining REC decoder work

**Status:** Implementing.

The implemented lifecycle, invocation, validation, models, and SDK boundaries
are documented in [REC decoding](../../docs/rec-decoding.md) and
[SDK integration](../../docs/sdk-integration.md). Only two requirements remain:

- [ ] **FR-021 — Architecture certification.** Build, self-test, and decode the
  approved corpus on each claimed Linux architecture. Linux aarch64 remains
  unvalidated; the separate macOS arm64 ACC observation does not close it.
  Preserve the same archive/digest/root/activation protections on every host.
- [ ] **FR-063 — Explicit payload adapters.** Replace reflection-derived sample
  structure with versioned project-owned contracts for each claimed category:
  record type, fields/nesting, units, nullability, integer/float/non-finite
  treatment, timestamps, binary encoding, warnings, and unsupported conditions.
  Unknown SDK properties must be ignored or produce a controlled contract
  mismatch, never opportunistically extend output.

Complete the applicable licensed local build/parser/corpus contracts: bind SDK
commit, source/output digests, counts/types, and adapter semantics; prove use of
the official parser; publish only scoped conclusions. Synthetic contracts must
continue to pass without SDK inputs. Follow the shared [gates](../README.md#shared-gates).

[Protected](../006-protected-rec-decoding/README.md) and
[batch](../007-rec-batch-decoding/README.md) decoding remain independent deferred
extensions. SPEC-005 consumes validation results; its deferred certification
program does not block this implementation.
