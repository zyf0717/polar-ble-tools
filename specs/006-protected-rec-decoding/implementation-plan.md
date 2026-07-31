# Implementation plan

Work remains deferred until the pinned SDK security strategies and approved
protected fixtures are available.

1. Inspect the pinned SDK contract without copying or translating its parser.
2. Approve the supported strategy and redacted public request model.
3. Implement protocol-v2 negotiation and bounded stdin requests.
4. Add owner-private CLI sources and immutable Python secret/provider models.
5. Construct the SDK security model only inside the JVM sidecar.
6. Add minimal-environment, redaction, timeout, cancellation, and malformed
   request/status tests.
7. Validate protected fixtures through SPEC-005 evidence controls.
