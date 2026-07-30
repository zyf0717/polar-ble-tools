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
| `cleanup_passive_files` | async | Delete hash-verified passive files through a date. |
| `doctor` | sync | Return `DoctorReport` for core, SDK-schema, and REC-decoder readiness. |
| `apply_ftu` | async | Apply a Loop Gen 2 `FtuProfile` or wear-location-only Verity Sense `VeritySenseFtuProfile`. |
| `ftu_status` | async | Return the Loop-style FTU completion state. |
| `physical_configuration` | async | Return Loop-style physical configuration or `None`. |
| `user_device_settings` | async | Return current user-device settings. |
| `update_user_device_settings` | async | Apply a `UserDeviceSettingsPatch`. |
| `diagnose_ftu` | async | Return FTU diagnostic fields. |

Specialized modules are deliberately separate from the top-level facade:

| Module | Public operations |
| --- | --- |
| `polar_ble_tools.collection` | Lower-level raw/passive collection APIs and result models. |
| `polar_ble_tools.bpb_decode` | `decode_bpb_file`, `decode_bpb_manifest`, `decode_passive_manifest`, path/schema helpers, and immutable decode results. |
| `polar_ble_tools.rec` | `decoder_status`, `verify_active_decoder`, `decode_recording`, `iter_decoded_records`, result models, and typed decode exceptions. |
| `polar_ble_tools.sdk_tools` | SDK staging/status/inspection, independent schema status/activation/provenance, and guarded removal through `remove_sdk_artifacts()`. |
| `polar_ble_tools.sdk_tools.generator` / `verifier` | Explicit schema generation and verification. |
| `polar_ble_tools.sdk_tools.decoder` | `build_decoder`, `verify_decoder`, `activate_decoder`, `remove_decoder`. |
| `polar_ble_tools.polar.setup` | `FtuProfile`, `VeritySenseFtuProfile`, `load_ftu_profile()`, validation, and lower-level `PolarSetupClient`. |
| `polar_ble_tools.polar.pmd` | Lower-level PMD measurement/control client. |

## Conventions

- Device-facing APIs are `async`; call them with `await` rather than
  `asyncio.run()` inside an existing event loop.
- Collection and listing results expose tuples rather than mutable internal
  lists. Raw/passive outcome fields use `StrEnum` models internally and retain
  their documented string values in `to_jsonable()` output.
- SDK and decoder actions are explicit. Importing any API never downloads,
  generates, builds, or activates local material.
- BPB decode results distinguish `decoded`, `unsupported`, and `failed`; stable
  failure codes classify schema, evidence, protobuf, date, and I/O failures.
  Decoded data preserves protobuf field and enum names. Schema provenance and
  derived logical dates remain separate result fields.
- `remove_sdk_artifacts()` requires full commit SHAs or `remove_all=True`;
  `include_decoders=True` also removes matching runtime/workspace entries but
  never the shared JDK. `retain_schemas=True` removes source only and requires
  verified format-3 schemas. The per-commit Gradle cache is part of the
  selected decoder workspace.
- `doctor()` is non-mutating. Use `DoctorReport.to_dict()` for the same stable
  representation produced by `polar-ble doctor`. Its non-fatal `warnings`
  identify active SDK/decoder commit mismatches and suggest rebuilding the
  decoder without marking a verified decoder unavailable.
- REC decoding raises a `RecDecodeError` subclass for unavailable, invalid,
  altered, incompatible, timed-out, or failed sidecars.

See the [CLI reference](cli-reference.md) for a command-to-API mapping.
