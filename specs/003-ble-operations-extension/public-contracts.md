# Public contracts

## CLI contract

The consolidated CLI remains canonical:

```text
polar-ble
├── discover
├── pair
├── connect
├── raw
│   ├── list
│   ├── types
│   ├── status
│   ├── settings
│   ├── start
│   ├── stop
│   ├── trigger get
│   ├── trigger set
│   ├── disk-space
│   ├── fetch
│   ├── collect
│   └── cleanup
├── passive
│   ├── list
│   ├── collect
│   └── cleanup
├── bpb
│   ├── decode
│   └── decode-manifest
├── rec
│   ├── status
│   ├── decode
│   ├── decode-tree
│   └── decode-manifest
├── ftu
├── sdk
└── doctor
```

Do not add compatibility aliases unless an existing external deployment is proven to require them.

Device-facing commands accept the existing target selector and optional
inventory restriction. Inventory is a CLI policy layer and is never required
by the Python APIs.

New command options are:

```text
polar-ble raw settings --type TYPE [--full]
polar-ble raw start --type TYPE [--setting KEY=VALUE ...]
  [--secret-file PATH | --secret-stdin] [--secret-strategy STRATEGY]
polar-ble raw stop --type TYPE
polar-ble raw trigger set --mode MODE [--type TYPE ...]
  [--setting KEY=VALUE ...]
  [--secret-file PATH | --secret-stdin] [--secret-strategy STRATEGY]
polar-ble raw fetch --path DEVICE_PATH --output LOCAL_PATH [--overwrite]

polar-ble passive collect --from-date DATE [--to-date DATE]
  [--domain DOMAIN ...] [--existing-file-policy skip|overwrite]
  [--delete-after-collect]
polar-ble passive cleanup --domain DOMAIN --delete-through DATE [--dry-run]

polar-ble rec decode INPUT --output OUTPUT [--overwrite] [--timeout SECONDS]
  [--secret-file PATH | --secret-stdin] [--secret-strategy STRATEGY]
polar-ble rec decode-tree INPUT_DIR [--output-dir DIR] [--overwrite]
  [--secret-file PATH | --secret-stdin] [--secret-strategy STRATEGY]
polar-ble rec decode-manifest MANIFEST --input-root DIR
  [--output-dir DIR] [--overwrite]
  [--secret-file PATH | --secret-stdin] [--secret-strategy STRATEGY]
```

Secret strategy is non-secret metadata and is accepted only when a secret
source is selected. The exact secret and sidecar rules are defined in
[REC sidecar and batch protocol](rec-protocol.md).

After argument parsing, machine-facing commands follow the JSON and exit-status
contract in [Models, errors, and workflow semantics](models-and-errors.md).

## Python contract

Prefer small workflow functions over exposing transport/session ownership to applications.

Conceptual exports:

```python
# Recording control
async def available_recording_types(target, *, runner=None): ...
async def recording_status(target, *, runner=None): ...
async def recording_settings(target, recording_type, *, full=False, runner=None): ...
async def start_recording(
    target, recording_type, *, settings=None, secret=None, runner=None
): ...
async def stop_recording(target, recording_type, *, runner=None): ...
async def offline_trigger(target, *, runner=None): ...
async def update_offline_trigger(
    target, trigger, *, secret=None, runner=None
): ...
async def device_disk_space(target, *, runner=None): ...
async def fetch_raw_recording(
    target, device_path, output, *, overwrite=False, runner=None
): ...

# Existing raw workflows
async def list_raw_recordings(target, *, runner=None): ...
async def collect_raw_recordings(target, ..., *, runner=None): ...
async def cleanup_raw_recordings(target, ..., *, runner=None): ...

# Passive workflows
async def list_passive_files(
    target, *, domains, from_date, to_date, runner=None
): ...
async def collect_passive_files(
    target,
    *,
    domains,
    from_date,
    to_date,
    root=None,
    existing_file_policy="skip",
    delete_after_collect=False,
    runner=None,
): ...
async def cleanup_passive_files(
    target,
    *,
    domain,
    delete_through,
    root=None,
    dry_run=False,
    runner=None,
): ...

# REC workflows
def decode_recording(
    source,
    destination,
    *,
    overwrite=False,
    timeout_seconds=None,
    secret=None,
): ...
def decode_recording_tree(
    input_dir,
    *,
    output_dir=None,
    overwrite=False,
    timeout_seconds=None,
    secret_provider=None,
): ...
def decode_recording_manifest(
    manifest,
    *,
    input_root,
    output_dir=None,
    overwrite=False,
    timeout_seconds=None,
    secret_provider=None,
): ...
def decoder_status(*, cache=None): ...
```

Requirements:

- device-facing APIs are asynchronous;
- local decode APIs may remain synchronous unless an existing async API is required;
- every API accepts test injection where the current architecture supports it;
- public return models expose stable `to_dict()` or `to_jsonable()` representations;
- public models contain no Bleak, protobuf, Kotlin, Gradle, or SDK-specific classes;
- public workflow functions delegate to cohesive subsystem services rather than growing one monolithic facade;
- internal refactoring may change private modules freely when documented public behavior remains stable.

`runner` accepts a `DeviceWorkflowRunner` for transport, lock-registry, and
global-limiter injection. `None` uses the process default. Local REC functions
do not acquire device locks.

Dates are `datetime.date` values in Python. Measurement types, trigger modes,
passive domains, settings, secrets, and result models are project-owned typed
objects; string convenience inputs normalize at the API boundary.

The conceptual result fields and immutability rules are normative in
[Models, errors, and workflow semantics](models-and-errors.md). Implementations
may use existing public model names where the serialized contract is identical.
