# Public contracts

## CLI

`polar-ble` is the canonical executable. Core operations are:

```text
polar-ble raw list|types|status|settings|start|stop
polar-ble raw trigger get|set
polar-ble raw disk-space|fetch|collect|cleanup
polar-ble passive list|collect|cleanup
```

After argument parsing, machine-facing success writes one deterministic JSON
document to stdout. Operational errors write diagnostics to stderr. Exit codes
are:

```text
0  operation completed under its result contract
1  operational, protocol, transport, storage, or partial failure
2  usage or pre-session validation failure
```

## Python

Common high-level async functions are exported from `polar_ble_tools`:

```python
available_recording_types
recording_status
recording_settings
start_recording
stop_recording
offline_trigger
update_offline_trigger
device_disk_space
fetch_raw_recording
list_raw_recordings
collect_raw_recordings
cleanup_raw_recordings
list_passive_files
collect_passive_files
cleanup_passive_files
```

Each device-facing call owns one workflow session unless the caller deliberately
uses lower-level clients. Listing/result collections are immutable tuples.
Project-owned enums remain comparable to their stable string values, while
serialized output contains plain strings and lists.

## Compatibility

Documented `0.3.0` support is limited to the device/operation matrix in
`docs/compatibility.md`. An exposed PMD/PFTP service is not by itself a support
claim.
