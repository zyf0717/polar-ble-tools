# Structured REC decoding

## Scope and support status

Structured decoding is an experimental, local-only capability. Raw `.REC`
retrieval remains independent of it. The sidecar accepts only unencrypted
recordings in the compatibility matrix; encrypted and unvalidated categories
are unsupported.

The public compatibility claim remains explicit unprotected decoding on Linux
x86_64. The lifecycle implementation now has pinned Linux aarch64 descriptors
and equivalent synthetic safety contracts, but a real aarch64 build/run remains
a protected validation gate. Protected recordings and expanded adapter
certification remain deferred to SPEC-004 and SPEC-005.

The project uses a local JVM sidecar because Polar's official REC parser is in
the separately licensed SDK. This keeps SDK classes, source, and binaries out
of the Python runtime and release artifacts while retaining a versioned,
project-owned JSONL boundary.

## Prerequisites

Use Linux x86_64, install the SDK extra, and explicitly stage the supported SDK:

```bash
python -m pip install "polar-ble-tools[sdk]"
polar-ble sdk install --accept-license
```

The first decoder build provisions architecture-specific, checksum-verified
Temurin JDK 21.0.12+8 and Gradle 9.4.1 in the user cache. Reuse requires a
descriptor-bound local manifest and unchanged executable digest. Nothing is
downloaded, built, or activated on import or by `sdk install`.

SDK installation records the exact staged source digest, licence filename and
digest, resolved revision, acceptance time, and project-owned acceptance method.
Decoder builds copy the exact SDK licence and required third-party listing into
the local decoder entry. Activation and status fail closed when either file,
path, or digest changes.

## Build and activate the local decoder

```bash
polar-ble sdk decoder build
polar-ble sdk decoder verify
polar-ble rec status
```

Builds create an isolated per-commit workspace. The JDK is persistent and
shared across commits. Activation executes the sidecar `version` and
`self-test` handshakes and preserves the previously active decoder on failure.
Use `--offline` only after the toolchain and Gradle dependencies are cached.

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

## Decode a tree or manifest

```bash
polar-ble rec decode-tree recordings/ --output-root decoded/
polar-ble rec decode-manifest recordings.jsonl \
  --root recordings/ --output-root decoded/
```

Tree mode selects readable regular `.REC` files case-insensitively, does not
follow symlinks, excludes its output subtree, preserves relative paths, and
orders work by relative POSIX path. Both modes preflight every destination
before starting the sidecar. Individual unsupported or failed recordings do not
stop later files; `summary.json` records deterministic outcomes and is
published atomically after processing.

The manifest is newline-terminated JSONL with one strict row per recording:

```json
{"schema_version": 1, "source": "relative/path/ACC.REC", "source_sha256": "optional lowercase SHA-256"}
```

Sources must be root-relative regular REC files. Absolute paths, traversal,
symlinks, duplicate sources or destinations, unknown fields, inline secrets,
unsupported schema versions, and digest mismatches fail the operation before
decoding. `secret_id` is reserved by the schema but requires the deferred
protected protocol and a configured provider.

## Python API

```python
from polar_ble_tools.rec import (
    decode_recording,
    decode_recording_manifest,
    decode_recording_tree,
    iter_decoded_records,
)

report = decode_recording("PPI0.REC", "PPI0.jsonl")
for record in iter_decoded_records("PPI0.jsonl"):
    print(record.record_type, record.timestamp_ns, record.payload)

tree = decode_recording_tree("recordings", "decoded")
manifest = decode_recording_manifest("recordings.jsonl", "recordings", "decoded-from-manifest")
```

`iter_decoded_records` validates the complete stream before yielding records
and uses two streaming passes, not whole-file JSON loading.

## Output protocol v1

The output is UTF-8 JSON Lines: exactly one header, zero or more records, and
one final summary. Header and status handshakes carry the protocol version,
decoder version, SDK commit, and source digest. Record types are lowercase
project-owned slugs; timestamps are integer Unix nanoseconds or `null`.
Malformed JSON, non-finite constants, invalid slugs, non-string warnings,
summary disagreement, and rows after the summary are rejected.

## Recording metadata and timestamps

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

## Security and distribution boundary

Manifests record digests for every runtime file and the JDK executable. The
project distributes only its Kotlin and Gradle templates. It does not distribute
Polar SDK source, recordings, generated schemas, JARs, classes, or a decoder
binary.

## Compatibility and limitations

See [compatibility](compatibility.md) for evidence-backed support claims. Local
fixture contracts use `POLAR_BLE_REC_FIXTURE_MANIFEST`, a private JSON file with
relative paths, source/output SHA-256 values, record type, and record count.
The manifest and recordings must not be committed. Decoder protocol-policy
changes require regenerating each affected private `expected_output_sha256`.
