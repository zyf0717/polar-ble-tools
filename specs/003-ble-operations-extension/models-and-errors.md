# Models, errors, and workflow semantics

This document defines the stable model and failure boundaries used throughout
SPEC-003.

## Model rules

Public result objects are frozen dataclasses or equivalent immutable models.
Collection fields serialize as arrays but are exposed as tuples or defensive
copies. Mapping fields are read-only or copied on construction.

Every public result model provides `to_dict()` or `to_jsonable()`. Serialization:

- uses project-owned field and enum names;
- emits paths as strings and UTC timestamps with a `Z` suffix;
- emits enum values as stable strings;
- sorts unordered device types, record types, and per-file results;
- includes optional fields with null where the contract lists them;
- never serializes transport, protobuf, SDK, Gradle, Java, or Kotlin objects.

Schema-versioned stored artifacts reject unsupported versions. Backward
readers may accept older versions only through an explicit migration path and
must never reinterpret an unknown field as deletion evidence.

## Local SDK acceptance provenance

The local SDK install manifest is a project-owned, local-only model. It binds
one explicit acceptance to one staged SDK content identity and copied licence
digest:

```text
sdk_commit
source_identity
license_filename
license_sha256
accepted_at
acceptance_method
```

`source_identity` is content-addressed for a user-supplied SDK path.
`accepted_at` is UTC and `acceptance_method` is a stable project-owned value,
such as `cli_flag`. The model records neither user identity, username,
hostname, shell history, machine identifier, nor telemetry. It is local cache
state and is excluded from public artifacts.

Acceptance is valid only when the staged SDK identity and licence filename and
digest exactly match the record. A change requires a new explicit acceptance;
the record cannot silently apply to another revision, source snapshot, or
licence text. Schema activation remains independent of decoder activation.

## Recording-control results

The high-level APIs return these conceptual immutable models:

```text
RecordingTypesResult
  device_id
  types

RecordingStatusResult
  device_id
  active_by_type
  observed_at

RecordingSettingsResult
  device_id
  recording_type
  full
  settings

RecordingCommandResult
  device_id
  recording_type
  operation                 start | stop
  active
  observed_at

OfflineTriggerResult
  device_id
  mode
  trigger_features
  observed_at

DeviceDiskSpaceResult
  device_id
  fragment_size
  total_fragments
  free_fragments
  total_bytes
  free_bytes
  used_bytes
  observed_at

RawFetchResult
  device_id
  device_path
  output_path
  fetched_size
  sha256
  observed_at
```

The API may return an existing lower-level frozen model where its fields and
serialization exactly satisfy this contract. It must not return a mutable PMD
settings dictionary owned by a session client.

## Passive results

Per-file collection status is one of:

```text
fetched
skipped
missing
ignored
failed
```

Per-file collection results contain domain, logical date, exact device path,
local path, fetched size, SHA-256, status, error code/message, deletion status,
deleted paths, and deletion error. Fields not applicable to the outcome are
null.

Collection summary counts are derived from, and must equal, the per-file
results:

```text
listed
fetched
skipped
missing
ignored
failed
deleted
delete_failed
```

`ok` is true only when `failed == 0` and `delete_failed == 0`. Missing optional
files do not make the run fail.

Cleanup results contain:

```text
device_id
output_dir
audit_path
selected
deleted
dry_run
blocked
failed
records
```

The counts must equal the stable deletion statuses in FR-019. `ok` is true
only when `blocked == 0` and `failed == 0`; a dry run of verified candidates is
successful.

## REC results

Single-file decode returns:

```text
source_path
destination_path
source_sha256
destination_sha256
sdk_commit
decoder_version
protocol_version
platform
architecture
record_count
record_types
warnings
```

`record_types` totals equal `record_count`. Warnings are ordered,
deduplicated project-owned strings. Batch models are defined in
[REC sidecar and batch protocol](rec-protocol.md).

Decoder status contains:

```text
available
verified
sdk_commit
decoder_version
protocol_versions
platform
architecture
verification_level
capabilities
reason
remediation
```

Status is read-only and performs no install, download, build, activation, or
repair.

## Error hierarchy

Subsystem errors retain their causal category:

```text
PolarBleToolsError
├── ValidationError
├── UnsupportedOperationError
├── DeviceWorkflowError
│   ├── DeviceConnectionError
│   └── DeviceTimeoutError
├── ProtocolError
│   ├── PmdProtocolError
│   └── PftpProtocolError
├── StorageError
│   ├── ManifestError
│   ├── VerificationError
│   └── PublicationError
├── SdkLifecycleError
│   ├── LicenseAcceptanceRequiredError
│   ├── LicenseAcceptanceMismatchError
│   ├── LicenseNoticeMissingError
│   └── LicenseNoticeMismatchError
└── RecDecodeError
    ├── DecoderUnavailableError
    ├── DecoderManifestError
    ├── DecoderVerificationError
    ├── DecoderProtocolError
    ├── DecoderTimeoutError
    ├── RecordingSecurityError
    ├── UnsupportedRecordingError
    └── RecordingDecodeError
```

Existing documented exceptions may remain subclasses or aliases for
compatibility. Broad command-layer translation must not collapse these
categories or replace transport failure with a generic per-file error.
Runtime cancellation is propagated as the async runtime's cancellation
sentinel and is not wrapped in this hierarchy.

Every stable error has:

```text
category
code
message
operation
retryable
```

The following stable codes are required where applicable:

```text
license_notice_missing
license_notice_mismatch
license_acceptance_required
license_acceptance_mismatch
sdk_output_contract_mismatch
```

Optional cause metadata may identify a project-owned subsystem, but never an
SDK class name or secret. `retryable` is false for validation, unsupported,
manifest-integrity, licence/notice-integrity, acceptance, and secret-invalid
errors; it may be true for transport and timeout errors when retry is safe.

## CLI output and exit behavior

After successful argument parsing, machine-facing commands write exactly one
JSON document to stdout. Diagnostics and the one structured error document go
to stderr. Progress messages never appear on stdout.

Exit status:

```text
0  operation completed under its result contract
1  operational, protocol, transport, storage, security, or partial-batch failure
2  command-line usage or pre-session validation error
```

Unsupported per-file batch results follow the batch rule and do not alone
produce exit status one. `rec status` returns zero even when unavailable because
unavailability is its reported state; malformed local state that prevents a
trustworthy status returns one.

CLI success and failure JSON are deterministic (`sort_keys=True` equivalent).
Argument-parser help and syntax diagnostics may retain the parser's standard
human-readable format.

## Device identity and locking

Device targets normalize before lock lookup. MAC addresses use uppercase
colon-separated form; non-MAC platform identifiers are trimmed stable strings.
Empty identities are validation errors.

The process-shared lock registry returns the same async lock for the same
normalized identity. A workflow acquires:

```text
per-device lock
→ optional global limiter
→ device session
→ session-scoped protocol operation lock where required
```

Acquisition and release are cancellation-safe. Locks are never held across
caller code after the workflow returns. The registry must not grow without
bound after short-lived device identities cease to be referenced.

Same-device public operations serialize for their entire session. Different
devices may progress concurrently up to the global limit. The runner owns no
retry policy and does not retry a destructive operation automatically.

## Session and cancellation behavior

One workflow invocation creates one connected session and session-scoped PMD,
PFTP, offline, and setup clients. Clients are invalid after context exit.

Cancellation is never converted into a successful partial result. Teardown is
shielded only long enough to perform bounded notification stop and disconnect;
the original cancellation is then re-raised. A cancelled destructive command
records an audit result only when a remove attempt was actually issued and its
outcome is known; otherwise it records `failed` with a redacted indeterminate
outcome and must not retry automatically.

## Time and ordering

Device file logical dates are device-local calendar dates. Audit, fetch,
decode, and status timestamps are UTC. The cleanup cutoff is compared with the
host's current local date as required by FR-017.

Listings, manifest selections, record-type maps, warnings, deletion candidates,
batch inputs, and serialized per-file results have explicit deterministic
ordering. Tests must not depend on filesystem enumeration, set iteration, or
callback arrival order.
