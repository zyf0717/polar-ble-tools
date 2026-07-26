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
- Generate protobuf schemas only through the explicit SDK workflow from the
  separately licensed schema inputs. Do not manually transcribe, reconstruct,
  translate, commit, package, or publish definitions, descriptors, or generated
  bindings.
- Keep generated schema outputs, SDK acceptance records, decoder licences, and
  decoder notices local to their respective caches. Schema activation and
  decoder activation remain independent.
- Keep protected REC decoding confined to the pinned official SDK parser inside
  the JVM sidecar. Do not translate parsing/decryption behavior, implement an
  independent REC parser or decryptor, patch SDK source, or use Python PMD
  secret/decryption behavior as a REC fallback.
- Use explicit project-owned REC payload adapters. Reflection may extract
  private SDK results but must not define public JSONL fields or nesting.
- Refactor touched code toward the ownership model in FR-046 before layering on new behavior.
- Keep command handlers thin and keep protocol, storage, security, and lifecycle rules in their owning modules.
- Reject abstractions that only rename duplication; introduce shared components only when they express a stable invariant.
- Keep each phase independently testable and commit in dependency order.
- Update tests and documentation with each public behavior change.
- Do not broaden scope to cloud or hub orchestration.
- Do not weaken deletion, cache, subprocess, artifact, or secret-safety checks to accelerate implementation.
- Do not upload restricted material through CI artifacts, dependency caches,
  container layers, Gradle scans, test or coverage reports, crash dumps, debug
  logs, SBOM/provenance bundles, temporary archives, or Git LFS.
- Keep real-device and participant data private; document protected fixture
  retention/deletion and redact evidence and failure reports.
- Do not position the package as diagnostic, clinical, medical-device,
  life-supporting, or life-critical software, and do not add telemetry.
- Do not claim compatibility from unit tests or prior observations alone.
- Stop and document a blocker where a vendor-supported path cannot be implemented inside the licensing and security boundary.

## Stop conditions

Stop the affected workstream and record the blocker if:

- Linux aarch64 support requires distributing or modifying Polar SDK source;
- an operation requires manually reproducing an SDK schema, descriptor, enum,
  field number, or generated binding;
- SDK generation is unavailable and the only proposed path is a hand-maintained
  schema fallback;
- encrypted decoding requires translating the vendor decoder, independently
  parsing REC metadata, independently decrypting REC content, copying protected
  parser logic, patching SDK source, or falling back to Python PMD decryption;
- a secret cannot be kept out of argv, logs, manifests, and output;
- the SDK does not expose the required secret-aware decode behavior;
- sidecar output cannot retain a versioned project-owned boundary;
- required decoder-local licence or notice material cannot be copied, hashed,
  verified, and kept out of public artifacts;
- licence acceptance cannot be bound to the exact staged SDK content and
  licence digest;
- passive deletion cannot be tied to exact locally verified files;
- a destructive device operation cannot be safely bounded and audited;
- a compatibility claim lacks controlled fixture or hardware evidence;
- required public evidence would disclose device, participant, profile, raw,
  decoded, or secret data;
- public CI or release workflows cannot prevent restricted material from being
  retained or uploaded through artifacts, caches, layers, reports, scans, or
  bundles;
- implementation would require changing the package’s SDK-distribution boundary.

A stopped optional workstream must not block unrelated safe development work. Document the resulting unsupported capability explicitly.

## Definition of done

SPEC-003 is complete when:

1. all recording-control operations are available through documented CLI and Python APIs;
2. passive collection supports guarded `delete-after-collect`;
3. passive cleanup is verified, date-bounded, domain-bounded, dry-runnable, and audited;
4. the REC sidecar builds and verifies on Linux x86_64 and Linux aarch64;
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
16. generated schemas are locally produced from separately licensed inputs,
    never manually reconstructed, and remain uncommitted/cache-only;
17. protected REC decoding uses only the pinned official SDK parser and explicit
    project-owned payload adapters;
18. decoder-local licence/notices and SDK acceptance provenance are present,
    content-bound, hashed, verified, and excluded from public outputs;
19. public CI, caches, container layers, scans, reports, bundles, Git LFS,
    distributions, and release assets contain no SDK source, generated SDK
    artifact, decoder binary, private fixture, payload, device identifier, or
    secret;
20. privacy, fixture-retention, evidence-redaction, passive-data, and
    non-medical-positioning requirements are satisfied.
