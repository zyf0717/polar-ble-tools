# 14. Testing strategy

### 14.1 Mandatory public CI tests

Use a project-owned fake sidecar executable. No Polar SDK or real decoder is required.

Add tests for:

- clean import with no decoder;
- unavailable status and remediation;
- valid manifest discovery;
- digest mismatch rejection;
- protocol version mismatch;
- malformed stdout status;
- malformed JSONL;
- missing header or summary;
- source digest mismatch;
- non-zero child exit;
- timeout and child termination;
- bounded stderr handling;
- atomic output;
- overwrite protection;
- temporary-file cleanup;
- record iteration;
- CLI exit behavior;
- active-decoder activation and rollback;
- decoder removal;
- `doctor` reporting;
- existing `raw` tests remaining unchanged.

### 14.2 Builder tests without vendor content

Create a tiny project-owned fake SDK/build fixture only if useful for build orchestration tests. It must not copy or approximate vendor decoder implementation.

Test:

- workspace generation;
- toolchain command construction;
- staging and activation;
- failed build rollback;
- final-artifact allowlisting;
- manifest generation;
- offline flag propagation.

### 14.3 Local SDK contract tests

Mark real SDK tests separately, for example:

```text
tests/sdk_decoder_contract/
```

They must be skipped unless explicitly enabled with local environment variables and prerequisites.

At minimum validate:

- adapter compiles against the pinned SDK commit;
- `version` and `self-test` succeed;
- one user-supplied sanitized `.REC` sample decodes;
- output passes Python protocol validation;
- output is deterministic across two runs;
- no SDK source or recording data appears in the final decoder directory.

Never commit personal or identifiable recordings. Commit a `.REC` fixture only after confirming provenance, sanitization, and redistribution suitability.

### 14.4 Packaging tests

Expand packaging artifact checks to fail if a wheel, sdist, release artifact, or repository-tracked output contains:

```text
*.jar
*.class
*.aar
decoder/polar/
decoder-build/polar/
cached SDK source
generated SDK schema output
local .REC samples
```

Project-authored `.kt`, `.kts`, or build templates are allowed only from the designated adapter template directory.

