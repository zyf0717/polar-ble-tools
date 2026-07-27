# Architecture

`polar-ble-tools` separates transport, protocol clients, device workflows,
collection, storage, decoding, and optional SDK tooling so each boundary can be
tested without hardware or downloaded schemas.

## Package boundaries

- `ble/` provides the transport protocol, Bleak backend, lifecycle state, and
  explicit BlueZ pairing helpers.
- `polar/pmd.py` implements PMD control-point requests, settings, status, and
  recording triggers.
- `polar/pftp.py` implements PFTP requests, RFC76 framing, directory and file
  operations, and synchronization notifications.
- `polar/offline.py`, `polar/passive.py`, and `polar/setup.py` expose
  recording, passive-file, FTU, and device-settings operations.
- `device.py` owns one BLE session and assembles the protocol services.
- `collection.py`, `raw_data/`, and `passive_data/` coordinate retrieval and
  durable storage without embedding transport logic in storage classes.
- `bpb_decode/` maps supported device paths to locally available protobuf
  messages and normalizes decoded output.
- `schemas/` and `sdk_tools/` manage explicit, user-initiated SDK discovery,
  schema generation, verification, and cache activation.
- `rec/` is the public, SDK-free facade for verified local REC sidecars.
- `sdk_tools/decoder/` builds, verifies, activates, and removes those sidecars
  without depending on raw collection.

## BLE lifecycle

Discovery is read-only. Pairing and connection select an explicit device
identifier, optionally constrained by an authorized-device inventory. BlueZ
pairing is released before a Bleak session opens the same peripheral. A device
session starts PMD and PFTP notifications, exposes service clients, and closes
both services and the transport on exit. Workflow locks serialize access to one
device and bound concurrent sessions globally.

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

Structured REC decoding is a separate Python-to-JVM process boundary. Python
validates the active decoder manifest, runtime-file digests, pinned JDK digest,
host platform, and sidecar handshake before invoking it. The sidecar receives a
source path and private output path, then returns a versioned JSONL stream.
Raw collection neither requires nor invokes this component. Decoder activation
and schema activation are independent, explicit state transitions.

## Optional SDK data

SDK installation is an explicit command. Source discovery, descriptor
inspection, dependency closure, generation, import normalization, verification,
and cache activation occur outside the repository and installed distribution.
Activation changes only after verification succeeds. Importing the package or
accessing a property never downloads or generates schemas.

The decoder cache separates per-commit workspaces and installed runtimes from a
shared pinned JDK. Installed manifests use relative cache paths and digests, so
they are portable within a user cache but reject altered runtimes.
