# Validation and documentation

Only SDK-free core BLE, packaging, and repository release gates are normative
for SPEC-003. Sidecar, protected SDK/fixture, and hardware-certification gates
below are transferred design inputs for SPEC-004 and SPEC-005.

## Test requirements

### SDK-free tests

Assert:

- imports succeed without SDK/cache/JDK/Gradle;
- recording-control functions use existing clients correctly;
- raw path, type, setting, trigger, date, domain, and secret-source validation
  happens before lock acquisition and opens no BLE session;
- raw fetch rejects traversal, invalid calendar segments, symlink output,
  aliasing, size mismatch, and unexpected overwrite;
- stop waits for inactive status and returns a typed timeout when the bounded
  poll expires;
- disk-space derived counters are internally consistent;
- device locks serialize same-device operations;
- different-device operations progress concurrently only up to the configured
  global limit;
- cancellation releases device locks, protocol operation locks, notification
  state, sessions, and limiter permits;
- CLI input errors open no BLE session;
- passive cleanup blocks unverified files;
- passive `skip` reverifies identity, domain, path, listed size, local size, and
  SHA-256;
- passive `overwrite` refetches, atomically replaces the local artifact, and
  appends rather than rewrites its manifest;
- delete-after-collect retains the latest observed logical date and every
  unknown-date record;
- passive cleanup selects the latest manifest row per exact path, never removes
  directories, and orders attempts deterministically;
- malformed manifests and completed malformed JSONL rows fail closed; an
  explicitly tolerated torn final audit/manifest row never becomes deletion
  evidence;
- dry-run opens no BLE session and mutates neither device nor local artifacts
  except the explicit dry-run audit record;
- passive sync stop uses `completed=true` only after a successful body and
  attempts termination after protocol failure or cancellation;
- per-file PFTP response failures continue while BLE transport failures abort;
- batch decode works with a fake sidecar;
- generated-schema absence reports unavailable and never activates a copied,
  reconstructed, transcribed, or hand-maintained schema fallback;
- schema-generation and decoder-build workflows are explicit and independent;
- SDK acceptance manifests bind `sdk_commit`, content identity, licence filename,
  digest, UTC time, and acceptance method without identity or host metadata;
- changed licence files, mismatched acceptance records, and changed staged
  content require explicit re-acceptance; an unchanged verified cache entry is
  reusable transactionally;
- no operation implicitly downloads or builds anything.

### Sidecar tests

Assert:

- Linux x86_64 and Linux aarch64 toolchain selection, including `amd64` and `arm64` alias
  normalization;
- checksum mismatch rejection;
- unsafe archive entry rejection;
- wrong-platform decoder rejection;
- transactional activation and rollback;
- exact `Polar_SDK_License.txt` and required upstream notices are copied from
  the resolved SDK revision into the staged decoder cache;
- missing licence, missing notice, modified licence/notice, escaping notice
  path, and unexpected replacement notice fail activation and verification;
- notice manifest paths/digests are cache-relative and removal deletes the
  decoder-local licence/notices with the cache entry;
- failed notice verification or promotion preserves the last verified decoder;
- protocol-v1 compatibility;
- protocol-v2 handshake and capability negotiation;
- protected requests use stdin and contain no input, output, or secret in argv;
- unknown fields, duplicate JSON keys, invalid UTF-8/base64, oversized
  requests/status/JSONL rows, and unsupported protocol versions are rejected;
- secret request redaction;
- canary secret bytes and their hexadecimal/base64 representations never occur
  in argv, environment, stdout, stderr, logs, exceptions, summaries, manifests,
  or filenames;
- malformed, partial, timed-out, and non-zero sidecar failures;
- timeout and cancellation terminate the complete process group and close all
  stream readers;
- JSONL header/record/summary ordering, provenance, digest, counts, types,
  finite-number handling, and no-rows-after-summary validation;
- each supported REC category uses an explicit project-owned adapter mapping;
  SDK property discovery, class names, property names, or reflection order
  cannot alter JSONL automatically;
- a newly observed SDK property fails with `sdk_output_contract_mismatch` or is
  ignored according to the declared mapping, and fixture expectations change
  only after an intentional output-version decision;
- source/output alias rejection;
- batch tree discovery ignores symlinks and its resolved output subtree;
- manifest traversal, absolute paths, duplicates, inline secrets, digest
  mismatch, torn final rows, and destination collisions fail preflight;
- overwrite replaces only previously validated project-owned outputs;
- unsupported-only, partial-failure, and summary-publication exit behavior;
- batch per-file and summary ordering remains deterministic.

### Protected SDK contracts

Against the pinned separately licensed SDK:

- build and verify the sidecar on each claimed architecture;
- run `version` and `self-test`;
- prove the adapter constructs the pinned SDK secret/security model inside the
  JVM and invokes the pinned SDK REC parser, rather than a project-authored
  parser or decryptor;
- decode each claimed private fixture category;
- validate encrypted fixtures separately;
- record the negotiated protocol, protected-decode capability, and security
  strategy for encrypted fixtures without recording a key or secret identifier;
- verify expected source/output SHA-256 and record counts;
- remove generated SDK/decoder material after the run;
- upload no SDK source, JARs, class files, recordings, decoded data, or secrets.

### Private fixture contracts

Run only in a protected environment with approved fixtures. Assert:

- each claimed category matches its explicit project-owned payload contract,
  units, nullability, numeric treatment, timestamp policy, and binary encoding;
- fixture and decoded-output SHA-256 values match only after an intentional
  protocol/schema or adapter-contract change;
- unknown SDK fields do not appear in JSONL opportunistically;
- real-device fixture sources, decoded outputs, profile content, identifiers,
  and secrets are not retained in public test output, logs, failure reports, or
  uploaded artifacts;
- retention and deletion of protected fixtures are recorded by the private
  validation environment.

### Hardware tests

Use controlled disposable recordings for destructive tests.

Required evidence must be redacted to:

```text
date
package commit/version
device family
host architecture
operation
pass/fail
approved limitation
```

Do not log MAC addresses, profile contents, raw payloads, decoded participant
data, secrets, or exact private paths. Real-device fixtures must be consented,
disposable, synthetic where possible, or otherwise approved for the test
purpose.

Passive evidence must distinguish time coverage from signal coverage. It must
not treat passive activity, automatic samples, or low-rate temperature as
evidence for raw ACC, PPG, continuous PPI, or equivalent waveform support.

### Release and workflow artifact audit

Wheel, sdist, repository history, workflow configuration, GitHub Actions
artifacts, CI and uploaded dependency caches, container/OCI image layers,
Gradle build scans, test reports, coverage bundles, crash dumps, debug logs,
SBOM/provenance bundles, retained temporary CI archives, Git LFS,
release-candidate bundles, and release assets must reject:

```text
*.jar
*.aar
*.class
*.kt copied from SDK
*.swift copied from SDK
SDK source directories
generated SDK protobuf modules
decoder runtime directories
JDK/Gradle archives
real REC/BPB fixtures
device inventories
FTU profiles
secrets
private compatibility manifests
SDK acceptance manifests
decoder-local licence/notice files
Polar_SDK_License.txt
```

Project-authored Kotlin adapter templates remain permitted.

The audit inspects workflow definitions and upload/cache configuration, not only
material that already exists in a built wheel or release bundle. Public CI uses
only synthetic inputs, fake sidecars, and project-authored fixtures. Protected
SDK compilation, fixtures, hardware tests, and compatibility contracts must
run locally or in an explicitly private environment that uploads no restricted
material.

## Documentation requirements

Update:

```text
README.md
RELEASE_NOTES.md
docs/architecture.md
docs/cli-reference.md
docs/python-api.md
docs/compatibility.md
docs/rec-decoding.md
docs/raw-file-retrieval.md
docs/offline-recording.md
docs/troubleshooting.md
```

Documentation must state:

- which capabilities require only the base package;
- which require generated schemas;
- which require the optional REC sidecar;
- which architectures are supported for sidecar build/run;
- how secrets are supplied safely;
- which device and record categories have actual evidence;
- that raw REC remains authoritative;
- that unsupported or unvalidated behavior is reported rather than inferred;
- that schemas are generated locally from separately licensed SDK inputs and
  are never manually reconstructed or shipped;
- that the optional REC sidecar uses the pinned official SDK parser and carries
  required licence/notice material only in its local cache entry;
- that the package is not diagnostic, clinical, medical-device, life-supporting,
  or life-critical software;
- that users remain responsible for applicable privacy and data-protection
  obligations;
- that protected fixtures and device/participant data remain private;
- release-facing text remains product-focused and contains no comparative
  migration framing.
