# Python API reference

Use the high-level exports from `polar_ble_tools` for common operations. APIs
that require a device are asynchronous and own the connection for one call;
pass a `transport_factory` in tests or custom integrations.

| Import | Kind | Purpose |
| --- | --- | --- |
| `discover_devices` | sync | Scan BLE advertisements. |
| `pair_device`, `connect_device`, `release_device_connection` | sync | BlueZ pairing and connection lifecycle. |
| `list_raw_recordings` | async | List device REC entries. |
| `available_recording_types` | async | Return supported offline recording types. |
| `recording_status` | async | Return offline recording activity by type. |
| `recording_settings` | async | Return current or full offline settings. |
| `start_recording`, `stop_recording` | async | Control one offline recording. |
| `offline_trigger`, `update_offline_trigger` | async | Read or replace offline trigger configuration. |
| `device_disk_space` | async | Return validated PFTP disk-space counters. |
| `fetch_raw_recording` | async | Atomically fetch one validated device REC path. |
| `collect_raw_recordings` | async | Retrieve and hash-store raw REC files. |
| `cleanup_raw_recordings` | async | Delete only verified raw recordings. |
| `PassiveDomain` | enum | Select passive BPB domains for listing and collection. |
| `list_passive_files` | async | List device passive BPB entries for a date range and domain set. |
| `collect_passive_files` | async | Retrieve and hash-store passive BPB files. |
| `doctor` | sync | Return `DoctorReport` for core, SDK-schema, and REC-decoder readiness. |
| `apply_ftu` | async | Apply `FtuProfile`, including its optional settings patch. |
| `ftu_status` | async | Return FTU completion state. |
| `physical_configuration` | async | Return physical configuration or `None`. |
| `user_device_settings` | async | Return current user-device settings. |
| `update_user_device_settings` | async | Apply a `UserDeviceSettingsPatch`. |
| `diagnose_ftu` | async | Return FTU diagnostic fields. |

Specialized modules are deliberately separate from the top-level facade:

| Module | Public operations |
| --- | --- |
| `polar_ble_tools.collection` | Lower-level raw/passive collection APIs and result models. |
| `polar_ble_tools.bpb_decode` | `decode_bpb_file`, `decode_bpb_manifest`, path/schema helpers. |
| `polar_ble_tools.rec` | `decoder_status`, `verify_active_decoder`, `decode_recording`, `iter_decoded_records`, result models, and typed decode exceptions. |
| `polar_ble_tools.sdk_tools` | SDK staging/status/inspection/removal. |
| `polar_ble_tools.sdk_tools.generator` / `verifier` | Explicit schema generation and verification. |
| `polar_ble_tools.sdk_tools.decoder` | `build_decoder`, `verify_decoder`, `activate_decoder`, `remove_decoder`. |
| `polar_ble_tools.polar.setup` | FTU data models, validation, and lower-level `PolarSetupClient`. |
| `polar_ble_tools.polar.pmd` | Lower-level PMD measurement/control client. |

## Conventions

- Device-facing APIs are `async`; call them with `await` rather than
  `asyncio.run()` inside an existing event loop.
- SDK and decoder actions are explicit. Importing any API never downloads,
  generates, builds, or activates local material.
- `doctor()` is non-mutating. Use `DoctorReport.to_dict()` for the same stable
  representation produced by `polar-ble doctor`.
- REC decoding raises a `RecDecodeError` subclass for unavailable, invalid,
  altered, incompatible, timed-out, or failed sidecars.

See the [CLI reference](cli-reference.md) for a command-to-API mapping.
