# 16. Implementation sequence

### Phase 0 — feasibility and decision record

1. Locate the official decode path in the pinned SDK.
2. Build the smallest external adapter manually in a temporary local workspace.
3. Decode one locally owned sample.
4. validate the preferred pure-JVM adapter; use Android/JVM only if that spike exposes an Android dependency.
5. write `decisions/rec-sidecar-feasibility.md`.
6. stop if any feasibility-gate condition fails.

**Gate:** no production adapter code before the decision record identifies a reproducible supported build path.

### Phase 1 — project-owned protocol and runtime

1. Create `polar_ble_tools.rec`.
2. Implement models, errors, manifest loading, status, subprocess runtime, JSONL validation, and atomic output.
3. Add a fake sidecar fixture.
4. Add comprehensive unit and CLI tests.
5. Add `polar-ble rec status|decode`.

**Gate:** all behavior works against the fake sidecar on public CI, with no SDK installation.

### Phase 2 — decoder cache and lifecycle

1. Extend `SdkCache`.
2. Add decoder manifest and active-manifest handling.
3. Add staged activation and rollback.
4. Add `sdk decoder status|verify|activate|remove`.
5. Extend `doctor`.
6. Add cache/lifecycle tests.

**Gate:** corrupt or failed decoder states cannot replace a previously valid active decoder.

### Phase 3 — reproducible local build

1. Add project-owned adapter and build templates.
2. Implement SDK/toolchain discovery.
3. Generate an isolated build workspace.
4. Build using the mode selected in Phase 0.
5. implement final-artifact allowlisting.
6. Add `sdk decoder build`.
7. Run structural verification before activation.
8. Add optional local SDK contract tests.

**Gate:** a clean local machine with documented prerequisites can build from the pinned SDK checkout and decode the validated sample.

### Phase 4 — hardening and documentation

1. Add malformed protocol, timeout, digest, path, rollback, and packaging tests.
2. Update all documentation and notices.
3. Confirm existing raw, BPB, schema, and SDK commands are unchanged.
4. Build wheel and sdist and inspect contents.
5. Run a full local end-to-end test.

**Gate:** definition of done is satisfied.

## 17. Definition of done

The feature is complete only when all of the following are true:

- [ ] `polar_ble_tools.rec` imports without optional tooling.
- [ ] Raw `.REC` retrieval remains fully usable without the decoder.
- [ ] `sdk install` does not build or activate a decoder.
- [ ] A decoder can be built explicitly from the supported local SDK revision.
- [ ] No vendor source or locally compiled decoder is tracked or distributed.
- [ ] Activation is atomic and rollback-safe.
- [ ] Runtime verifies provenance, protocol, and executable digest.
- [ ] Decode output uses validated protocol-v1 JSONL.
- [ ] Failed decoding leaves no successful-looking partial destination.
- [ ] The Python API and CLI return actionable errors.
- [ ] Public tests use only fake/project-owned fixtures.
- [ ] Local SDK contract tests pass against the pinned revision.
- [ ] Wheel and sdist artifact scans pass.
- [ ] Documentation clearly states prerequisites, support boundaries, and licensing separation.
- [ ] `ruff check .`, `pytest`, `python -m build`, and `twine check dist/*` pass.

## 18. Agent execution rules

1. Work only on `feat/rec-decoder-sidecar`.
2. Implement phases in order and keep each phase independently reviewable.
3. Prefer small commits with tests:
   - `docs: record REC decoder sidecar feasibility`
   - `feat(rec): add sidecar protocol and runtime`
   - `feat(sdk): add decoder cache lifecycle`
   - `feat(sdk): build local REC decoder sidecar`
   - `docs: document optional REC decoding`
4. Do not modify raw collection semantics or couple decode to retrieval.
5. Do not add new mandatory Python dependencies unless unavoidable and justified.
6. Do not commit SDK content, compiled outputs, build caches, or real recordings.
7. Do not weaken existing artifact-separation tests.
8. Do not silently fall back to unverified decoders.
9. Do not guess official SDK APIs; record exact findings in the feasibility decision.
10. When blocked by SDK/toolchain constraints, stop with a precise report rather than translating vendor code.
11. Before completion, inspect `git status`, the complete diff, wheel contents, and sdist contents.
12. Include in the PR description:
    - supported SDK commit;
    - build mode and prerequisites;
    - protocol version;
    - local validation performed;
    - explicit confirmation that no SDK or decoder binary is distributed.

## 19. Recommended release boundary

Release as `0.2.0`, not a `0.1.x` patch, because this adds:

- a new public Python namespace;
- new CLI commands;
- a versioned sidecar protocol;
- a new optional local toolchain lifecycle.

The decoder remains experimental until compatibility is validated across more than one recording type and device. Mark unsupported record types clearly rather than silently emitting incomplete data.
