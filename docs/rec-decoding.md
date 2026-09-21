# Structured REC decoding

## Scope and support status

Structured decoding is an experimental, local-only capability. Raw `.REC`
retrieval remains independent of it. The sidecar accepts only unencrypted
recordings in the compatibility matrix; encrypted and unvalidated categories
are unsupported.

The public compatibility claim covers explicit unprotected decoding on Linux
x86_64, macOS arm64, and Windows x86_64. The lifecycle has pinned Linux and
macOS descriptors for x86_64 and arm64 plus Windows x86_64; other
host/architecture combinations remain unvalidated. Protected and batch
decoding are not implemented. Explicit stable per-category payload adapters
and broader architecture certification remain incomplete.

The project uses a local JVM sidecar because Polar's official REC parser is in
the separately licensed SDK. This keeps SDK classes, source, and binaries out
of the Python runtime and release artifacts while retaining a versioned,
project-owned JSONL boundary.

The Python implementation keeps public models and errors, sidecar process
control, JSONL validation, and constrained publication in separate modules.
The public API continues to be exported from `polar_ble_tools.rec`. The JVM
template independently separates command dispatch, official-SDK parsing,
payload adaptation, JSONL encoding, and atomic publication; all template inputs
remain bound by the adapter source digest.

## Prerequisites

Use Linux or macOS on x86_64 or arm64, or Windows on x86_64. Install the SDK
extra and explicitly stage the supported SDK:

```bash
python -m pip install "polar-ble-tools[sdk]"
polar-ble sdk install
```

Proceeding at each install/download prompt accepts the Polar BLE SDK licence for
that invocation, including cache reuse; use `-y` for unattended installation.
No acceptance record is stored.

The first decoder build provisions architecture-specific, checksum-verified
Temurin JDK 21.0.12+8 and Gradle 9.4.1 in the user cache. Reuse requires a
descriptor-bound local manifest and unchanged executable digest. Nothing is
downloaded, built, or activated on import or by `sdk install`.

## Build and activate the local decoder

```bash
polar-ble sdk decoder build
polar-ble sdk decoder verify
polar-ble rec status
```

Builds create an isolated per-commit workspace. The JDK is persistent and
shared across commits. Activation executes the sidecar `version` and
`self-test` handshakes and preserves the previously active decoder on failure.
Use `--offline` only after the toolchain and Gradle dependencies are cached;
missing verified artifacts fail with no network access. Safe extraction rejects
absolute/traversing members, device nodes, unsafe links, and unexpected roots.
Descriptors bind host/architecture, archive names/URLs/roots/SHA-256, executable
path, and tool versions. Host aliases normalize `amd64` to `x86_64`, `arm64` to
`aarch64`, and macOS to `darwin`; macOS JDKs use `Contents/Home/bin/java`.
Windows uses the pinned Temurin ZIP, `java.exe`, Gradle's native batch launcher,
and a silenced generated decoder batch launcher so stdout remains JSON-only.

The build copies the exact `Polar_SDK_License.txt` from the pinned local SDK
checkout into the decoder runtime as attribution material. Its SHA-256 and SDK
commit are recorded in the decoder manifest. This is not an acceptance record
and does not replace fresh consent on any later SDK install/download invocation.
Its manifest entry has `purpose: attribution` and `is_acceptance_record: false`.
Older package-managed decoder caches without this attribution contract must be
rebuilt. Manually or externally managed sidecars are outside this package's
lifecycle and compatibility scope.

> **Redistribution warning:** Do not redistribute the locally compiled decoder
> under the `polar-ble-tools` Apache-2.0 licence alone. The local build contains
> or links material governed by the Polar BLE SDK licence.

## Check status

`polar-ble rec status` reports unavailable rather than failing when the active
manifest, runtime files, JDK, platform, or handshake cannot be verified.
Rebuild the decoder after changing any local runtime file.

## Decode a recording

```bash
polar-ble rec decode PPI0.REC --output PPI0.jsonl
```

The destination is prepared in an owner-private sibling directory. Without an
explicit overwrite option, publication uses atomic no-clobber semantics.
Timeouts terminate the full sidecar process group.
Decoding rejects an output that resolves to, or is a hard link to, the source
recording, even with `--overwrite`; the source `.REC` is never modified.
Overwrite accepts only an existing project-owned decoded JSONL stream that
passes header, record, and summary validation.

## Python API

```python
from polar_ble_tools.rec import (
    decode_recording,
    iter_decoded_records,
)

report = decode_recording("PPI0.REC", "PPI0.jsonl")
for record in iter_decoded_records("PPI0.jsonl"):
    print(record.record_type, record.timestamp_ns, record.payload)
```

`iter_decoded_records` validates the complete stream before yielding records
and uses two streaming passes, not whole-file JSON loading.

## Output protocol v1

Before decode, Python verifies the sidecar `version` handshake and invokes:

```text
<decoder> decode --input <source.REC> --output <staged.jsonl> --protocol 1
```

The process uses an argument array, a positive timeout, concurrent bounded
stdout/stderr drains, and a new POSIX process session. Stdout returns one bounded
JSON status object; stderr is diagnostic only. Timeout terminates the whole
process group, waits a bounded grace period, then kills if needed; no output
is published. The environment inherits the caller's variables with `JAVA_HOME`
and `PATH` set for the pinned JDK. Protocol v1 carries no secrets.

UTF-8 output contains exactly these row shapes, in order:

```json
{"type":"header","protocol_version":1,"sdk_commit":"40 lowercase hexadecimal characters","decoder_version":"project version","source_sha256":"64 lowercase hexadecimal characters"}
{"type":"record","record_type":"project_owned_snake_case","timestamp_ns":0,"payload":{}}
{"type":"summary","record_count":1,"record_types":{"project_owned_snake_case":1},"warnings":[]}
```

There may be zero or more record rows. Timestamps are integer Unix nanoseconds
or null where SDK semantics do not establish absolute time. Payloads contain
JSON scalars, arrays, and objects. Non-finite SDK numbers become null plus a
warning; Python rejects non-standard numeric constants.

Before publication, validate regular-file/symlink safety, line-byte bounds,
UTF-8, finite JSON, row order, record envelopes/slugs, source digest, SDK and
protocol provenance, record/per-type totals, string warnings, and EOF immediately
after summary. [Publication rules](#decode-a-recording) apply to every output.

The sidecar invokes the pinned official parser; project code must not parse REC
headers/payloads independently, decompress/decrypt content, translate or patch
SDK parsing logic, or provide a Python fallback.

## Recording metadata and timestamps

The current adapter maps measurement types and timestamp policy explicitly,
but discovers iterable SDK result properties and sample payloads through
reflection. Payload fields remain experimental; reflection order and newly
seen SDK properties do not establish a stable public schema.

The sidecar should preserve recording-level metadata when the pinned SDK model
provides it. Do not infer UTC from a timezone-less SDK value. HR samples have
no validated per-sample timestamp. Every PPI record currently emits
`timestamp_ns: null`, regardless of device, and the sidecar emits one summary
warning. The raw SDK `time_stamp` remains in the payload. Consumers must treat
the PPI envelope timestamp as absent until its SDK semantics are proven.

## Cache and removal

Decoder commands accept only a full lowercase 40-character SDK commit SHA.
Removal is constrained to the decoder cache and also removes that commit's
workspace; it never removes the shared JDK automatically.

`polar-ble sdk remove` retains decoders by default. Use repeated `--commit`
arguments or `--all` together with `--include-decoders` to remove corresponding
decoder runtimes and workspaces in the same guarded plan. Add `--dry-run` to
inspect the plan first. The shared JDK remains untouched; per-commit Gradle
files are removed with the selected workspace.

## Security and distribution boundary

Manifests bind manifest/protocol/decoder/package versions, SDK commit,
platform/architecture, JDK/Gradle versions and archive digests, toolchain descriptor
and adapter-source digests, verification level, executable path/digest,
runtime-file allowlist, and licence attribution. Runtime relative paths stay
inside the per-commit entry; the JDK stays inside its host toolchain cache.
Reverify every runtime file, JDK executable, host, SDK/protocol identity, and
handshake before decode. A mismatch reports unavailable or verification failure
with a rebuild command; it never silently chooses another decoder. The
project distributes only its Kotlin and Gradle templates. It does not distribute
Polar SDK source, `Polar_SDK_License.txt`, recordings, generated schemas, JARs,
classes, or a decoder binary in PyPI artifacts.

## Compatibility and limitations

See [compatibility](compatibility.md) for evidence-backed support claims. Local
fixture contracts use `POLAR_BLE_REC_FIXTURE_MANIFEST`, a private JSON file with
relative paths, source/output SHA-256 values, record type, and record count.
The manifest and recordings must not be committed. Decoder protocol-policy
changes require regenerating each affected private `expected_output_sha256`.

## Models and errors

`DecoderStatus` records availability/verification, SDK commit, protocol version,
verification level, and unavailable reason. Single-file results include
source/output paths and digests, SDK/decoder provenance, counts/types, and
ordered project-owned warnings.

`RecDecodeError` subclasses are `DecoderUnavailableError`, `DecoderManifestError`,
`DecoderVerificationError`, `DecoderProtocolError`, `DecoderTimeoutError`,
`UnsupportedRecordingError`, and `RecordingDecodeError`. Sidecar status codes
are project-owned; bounded stderr is not an automation contract.
