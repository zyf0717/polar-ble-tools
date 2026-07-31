# Architecture

`polar-ble-tools` separates transport, protocol clients, device workflows,
collection, storage, decoding, and optional SDK tooling so each boundary can be
tested without hardware or downloaded schemas.

## Package boundaries

- `ble/` provides platform-neutral models, structured discovery, native-device
  resolution, the Bleak backend, lifecycle state, and the narrow Linux BlueZ
  authentication-agent adapter.
- `polar/pmd.py` implements PMD control-point requests, settings, status, and
  recording triggers.
- `polar/pftp.py` implements PFTP requests, RFC76 framing, directory and file
  operations, and synchronization notifications.
- `polar/offline.py`, `polar/passive.py`, and `polar/setup.py` expose
  recording, passive-file, FTU, and device-settings operations.
- `device.py` owns one BLE session and assembles the protocol services.
- `collection.py`, `raw_data/`, and `passive_data/` coordinate retrieval and
  durable storage without embedding transport logic in storage classes.
- `bpb_decode/` maps supported device paths to locally generated official
  protobuf messages, preserves schema-faithful JSON, and keeps derived passive
  metadata separate.
- `schemas/` and `sdk_tools/` manage explicit, user-initiated SDK discovery,
  schema generation, verification, and cache activation.
- `rec/` is the public, SDK-free facade for verified local REC sidecars.
- `sdk_tools/decoder/` builds, verifies, activates, and removes those sidecars
  without depending on raw collection.

## BLE lifecycle

Discovery is read-only and maps structured Bleak advertisements to immutable
public records. MAC addresses and UUIDs are normalized; other identifiers are
opaque. A per-event-loop resolver coalesces concurrent resolution scans and
passes only current-context native `BLEDevice` objects to `BleakClient`; native
objects are neither public nor retained between operations.

Preparation, probe, PMD, PFTP, raw, passive, and FTU paths use the same workflow
ownership boundary. A device session verifies PMD and PFTP before becoming
ready, exposes the protocol clients, and closes the transport on exit. Locks
serialize one normalized identity, while a per-event-loop semaphore permits at
most two distinct device sessions. Each resolution, connection, readiness,
preparation, and disconnect phase is bounded.

Fresh Linux preparation is the sole OS-adapter exception. A temporary
`org.bluez.Agent1` implementation accepts only confirmation and supported
service authorization for the exact selected device. It rejects PIN/passkey,
unexpected-device, and unrelated-service requests and unregisters after every
outcome. Bleak continues to own discovery, pairing, service readiness, and
disconnect. No subprocess output is parsed and the package never removes host
bonds or changes adapter policy.

## Data flow

PMD controls measurement and offline-recording state. PFTP lists and transfers
device files. Raw `.REC` retrieval does not require generated schemas. Passive
`.BPB` retrieval is also schema-free; structured BPB decoding loads only a
verified active local schema cache.

Stores write payloads atomically, append manifests with size and SHA-256
metadata, verify local files with a shared streaming SHA-256 helper, constrain
stored paths to their configured roots, and tolerate a truncated final JSONL
record. Raw and passive stores share these low-level mechanics but retain
separate manifests, eligibility, and audit policy. Device cleanup uses exact
paths selected from the device listing. A file is eligible for deletion only
when its recording is inactive where applicable and its local copy matches the
recorded size and digest. Dry runs and deterministic deletion logs are
preserved.

Public collection results are frozen models with tuple-valued record
collections. Internal outcome enums serialize to stable strings at JSON/CLI
boundaries. Per-file protocol failures may produce failed records; BLE
transport failures abort the workflow.

Optional passive decoding starts only after raw collection and manifest
publication complete. It re-verifies raw size and SHA-256, writes owner-private
JSON atomically, and appends a version-2 evidence row containing schema/output
provenance. Cleanup-relevant dates are derived only from known payload fields;
payload/path disagreement is a decode failure. Version-1 raw rows remain
readable.

Structured REC decoding is a separate Python-to-JVM process boundary. Python
validates the active decoder manifest, runtime-file digests, pinned JDK digest,
host platform, and sidecar handshake before invoking it. The sidecar receives a
source path and private output path, then returns a versioned JSONL stream.
Raw collection neither requires nor invokes this component. REC-decoder,
generated-schema, and retained SDK-source activation are independent, explicit
state transitions. BPB decoding uses Python protobuf bindings directly and
does not use the JVM REC sidecar.

## Optional SDK data

SDK installation is an explicit command. Source discovery, descriptor
inspection, dependency closure, generation, import normalization, verification,
and cache activation occur outside the repository and installed distribution.
Activation changes only after verification succeeds. Importing the package or
accessing a property never downloads or generates schemas.

Generated-schema manifest format 3 binds the SDK source content digest,
revision metadata, descriptor digest, generated-file digests, dependency
closure, resolved symbols, and toolchain. Its independent active pointer allows
verified schemas to remain usable after explicit SDK-source removal. Legacy
format-2 caches remain source-bound until regenerated.

The decoder cache separates per-commit workspaces and installed runtimes from a
shared pinned JDK. Installed manifests use relative cache paths and digests, so
they are portable within a user cache but reject altered runtimes.

SDK cleanup is planned per full commit SHA across SDK source and generated
schemas. Matching decoder runtimes and workspaces remain independent and are
included only by explicit request. Multi-revision and all-revision cleanup
preflights every exact cache path before deletion and never implicitly removes
the shared decoder JDK. Source-only removal may retain a verified format-3
schema cache and its activation pointer.
