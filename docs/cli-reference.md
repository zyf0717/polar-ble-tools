# CLI reference

All commands are available through `polar-ble`. Use `polar-ble COMMAND --help`
for argument details; this reference defines the command surface and whether a
direct Python API is available.

| Command | Operation | Direct Python entry point |
| --- | --- | --- |
| `discover` | Scan BLE advertisements | `discover_devices()` |
| `pair` | Pair, bond, and trust a device | `pair_device()` |
| `connect` | Connect a paired device | `connect_device()` |
| `raw list` | List device REC files | `await list_raw_recordings()` |
| `raw collect` | Retrieve/hash-store REC files | `await collect_raw_recordings()` |
| `raw cleanup` | Safely remove verified device files | `await cleanup_raw_recordings()` |
| `passive list` | List passive BPB files | `await list_passive_files()` |
| `passive collect` | Retrieve/hash-store passive files | `await collect_passive_files()` |
| `bpb decode` | Decode one local BPB file | `decode_bpb_file()` |
| `bpb decode-manifest` | Decode BPB files named by a manifest | `decode_bpb_manifest()` |
| `ftu dry-run` | Validate an FTU profile without a device | `FtuProfile.from_json_file()` |
| `ftu apply` | Apply FTU profile and initial settings | `await apply_ftu()` |
| `ftu status` | Read FTU completion | `await ftu_status()` |
| `ftu physical-config` | Read physical configuration | `await physical_configuration()` |
| `ftu settings get` | Read user-device settings | `await user_device_settings()` |
| `ftu settings set` | Patch user-device settings | `await update_user_device_settings()` |
| `ftu diagnose` | Read FTU diagnostic state | `await diagnose_ftu()` |
| `sdk download` | Stage SDK source only | `install_sdk(..., activate=False)` |
| `sdk install` | Stage, inspect, generate, verify, activate schemas | Compose `install_sdk`, `inspect_sdk`, `generate_schemas`, `verify_schemas`, `activate_sdk` |
| `sdk status` | Show staged/active revisions | `sdk_status()` |
| `sdk inspect` | Inspect active SDK descriptors | `inspect_active_sdk()` |
| `sdk generate` | Generate schemas for active SDK | `generate_active_schemas()` |
| `sdk verify` | Verify active schemas | `verify_active_schemas()` |
| `sdk remove` | Remove one/all SDK cache entries | `remove_sdk()` / `remove_all_sdk_cache()` |
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
