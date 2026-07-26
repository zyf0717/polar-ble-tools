# Execution rules and completion

## Agent execution rules

- Work from current `polar-ble-tools` `main`.
- Do not import, cherry-pick, or copy wholesale from external implementation
  sources, and do not preserve another architecture merely for similarity.
- Keep package metadata, public documentation, release notes, changelogs, PyPI
  text, CLI help, generated artifacts, commit messages, and compatibility
  claims focused on `polar-ble-tools`.
- Prefer current `polar-ble-tools` clients and models over introducing parallel
  orchestration code.
- Refactor touched code toward the ownership model in FR-046 before layering on new behavior.
- Keep command handlers thin and keep protocol, storage, security, and lifecycle rules in their owning modules.
- Reject abstractions that only rename duplication; introduce shared components only when they express a stable invariant.
- Keep each phase independently testable and commit in dependency order.
- Update tests and documentation with each public behavior change.
- Do not broaden scope to cloud or hub orchestration.
- Do not weaken deletion, cache, subprocess, artifact, or secret-safety checks to accelerate implementation.
- Do not claim compatibility from unit tests or prior observations alone.
- Stop and document a blocker where a vendor-supported path cannot be implemented inside the licensing and security boundary.

## Stop conditions

Stop the affected workstream and record the blocker if:

- ARM64 support requires distributing or modifying Polar SDK source;
- encrypted decoding requires translating the vendor decoder;
- a secret cannot be kept out of argv, logs, manifests, and output;
- the SDK does not expose the required secret-aware decode behavior;
- sidecar output cannot retain a versioned project-owned boundary;
- passive deletion cannot be tied to exact locally verified files;
- a destructive device operation cannot be safely bounded and audited;
- a compatibility claim lacks controlled fixture or hardware evidence;
- implementation would require changing the package’s SDK-distribution boundary.

A stopped optional workstream must not block unrelated safe development work. Document the resulting unsupported capability explicitly.

## Definition of done

SPEC-003 is complete when:

1. all recording-control operations are available through documented CLI and Python APIs;
2. passive collection supports guarded `delete-after-collect`;
3. passive cleanup is verified, date-bounded, domain-bounded, dry-runnable, and audited;
4. the REC sidecar builds and verifies on Linux x86-64 and Linux ARM64;
5. batch tree and manifest decoding produce deterministic validated outputs and summaries;
6. controlled secret-protected REC fixtures decode without secret leakage, or the unsupported SDK limitation is explicitly recorded and accepted;
7. compatibility documentation matches protected evidence for Loop Gen 2 and Verity Sense;
8. same-device serialization and two-device concurrency are validated;
9. touched modules conform to the responsibility boundaries in FR-046;
10. avoidable duplicate orchestration, parsing, storage verification, path safety, digest, JSON publication, and sidecar invocation logic has been removed within scope;
11. public APIs use typed project-owned models and errors while private module structure remains free to evolve;
12. tests validate stable contracts without unnecessarily coupling to implementation details;
13. ordinary, packaging, SDK-contract, private-fixture, and protected hardware gates pass on the integration commit;
14. release-ready artifacts can be produced from the exact validated commit when a release is selected;
15. release-facing documentation remains product-focused and contains no
    comparative migration framing;
16. no SDK source, generated SDK artifact, decoder binary, private fixture, payload, device identifier, or secret appears in Git, public CI artifacts, distributions, or release assets.
