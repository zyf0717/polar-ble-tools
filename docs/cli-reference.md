# CLI reference

All commands are available through `polar-ble`. Use `polar-ble COMMAND --help`
for argument details; this reference defines the command surface and whether a
direct Python API is available.

| Command | Operation | Direct Python entry point |
| --- | --- | --- |
| `discover` | Scan BLE advertisements | `discover_devices()` |
| `pair` | Pair, bond, trust, verify connectivity, and disconnect | `pair_device()` |
| `connect` | Connect a paired device | `connect_device()` |
| `raw list` | List device REC files | `await list_raw_recordings()` |
| `raw types` | List supported offline recording types | `await available_recording_types()` |
| `raw status` | Read offline recording activity | `await recording_status()` |
| `raw settings --type TYPE [--full]` | Read offline recording settings | `await recording_settings()` |
| `raw start --type TYPE [--setting KEY=VALUE ...]` | Start an offline recording | `await start_recording()` |
| `raw stop --type TYPE` | Stop an offline recording and wait for inactivity | `await stop_recording()` |
| `raw trigger get` | Read offline trigger configuration | `await offline_trigger()` |
| `raw trigger set --mode MODE [--type TYPE ...] [--setting KEY=VALUE ...]` | Replace offline trigger configuration | `await update_offline_trigger()` |
| `raw disk-space` | Read device PFTP disk-space counters | `await device_disk_space()` |
| `raw fetch --path DEVICE_PATH --output LOCAL_PATH` | Atomically fetch one REC file | `await fetch_raw_recording()` |
| `raw collect` | Retrieve/hash-store REC files | `await collect_raw_recordings()` |
| `raw cleanup` | Safely remove verified device files | `await cleanup_raw_recordings()` |
| `passive list` | List passive BPB files | `await list_passive_files()` |
| `passive collect [--existing-file-policy skip\|overwrite] [--delete-after-collect] [--decode]` | Retrieve/hash-store passive files, then optionally decode the persisted manifest | `await collect_passive_files()`, `decode_passive_manifest()` |
| `passive cleanup --domain DOMAIN --delete-through YYYY-MM-DD [--dry-run]` | Delete verified passive files through a date | `await cleanup_passive_files()` |
| `bpb decode` | Decode one local BPB file | `decode_bpb_file()` |
| `bpb decode-manifest` | Decode BPB files named by a manifest | `decode_bpb_manifest()` |
| `bpb decode-passive-manifest` | Decode and enrich the latest rows in a passive manifest | `decode_passive_manifest()` |
| `ftu dry-run` | Validate an FTU profile without a device | `FtuProfile.from_json_file()` |
| `ftu apply` | Apply FTU profile and initial settings | `await apply_ftu()` |
| `ftu status` | Read FTU completion | `await ftu_status()` |
| `ftu physical-config` | Read physical configuration | `await physical_configuration()` |
| `ftu settings get` | Read user-device settings | `await user_device_settings()` |
| `ftu settings set` | Patch user-device settings | `await update_user_device_settings()` |
| `ftu diagnose` | Read FTU diagnostic state | `await diagnose_ftu()` |
| `sdk download` | Stage SDK source only | `install_sdk(..., activate=False)` |
| `sdk install` | Stage, inspect, generate, verify, and independently activate SDK source and schemas | Compose `install_sdk`, `inspect_sdk`, `generate_schemas`, `verify_schemas`, `activate_sdk`, `activate_schemas` |
| `sdk status` | Show staged SDK source and active source/schema revisions | `sdk_status()`, `schema_status()` |
| `sdk inspect` | Inspect active SDK descriptors | `inspect_active_sdk()` |
| `sdk generate` | Generate schemas for active SDK | `generate_active_schemas()` |
| `sdk verify` | Verify active schemas | `verify_active_schemas()` |
| `sdk schemas status` | Show independent generated-schema state | `schema_status()` |
| `sdk schemas verify [--commit SHA]` | Verify active or selected generated schemas | `verify_schemas()` |
| `sdk schemas activate --commit SHA` | Activate a verified generated-schema cache | `activate_schemas()` |
| `sdk remove --commit SHA [--commit SHA ...] [--retain-schemas] [--include-decoders] [--dry-run]` | Remove exact SDK revisions, optionally retaining format-3 schemas or including matching decoders | `remove_sdk_artifacts()` |
| `sdk remove --all [--include-decoders] [--dry-run] [--yes]` | Remove every selected cache revision with bulk confirmation | `remove_sdk_artifacts()` |
| `sdk decoder build` | Build optional REC sidecar | `build_decoder()` |
| `sdk decoder verify` | Execute sidecar handshakes | `verify_decoder()` |
| `sdk decoder status` | Check sidecar availability | `decoder_status()` |
| `sdk decoder activate` | Activate an installed sidecar | `activate_decoder()` |
| `sdk decoder remove` | Remove sidecar/workspace | `remove_decoder()` |
| `rec status` | Check active REC sidecar | `decoder_status()` |
| `rec decode` | Decode local REC into JSONL | `decode_recording()` |
| `doctor` | Report core/SDK/decoder readiness | `doctor()` |

The command wrappers remain available as `*_main(argv)` functions and
`polar_ble_tools.commands.main.main(argv)`, but they are intended for process
entry points and compatibility testing—not application integration.
