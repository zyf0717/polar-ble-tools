# Configuration and command line

All device operations select an explicit platform-neutral identifier.
Keep device inventories, profiles, captures, and credentials outside version
control.

## Discovery and authorization

Discovery reports only live BLE scan observations; it does not pair, connect,
trust, or otherwise alter a device:

```bash
polar-ble discover --timeout 15 --name Polar
```

Confirm the returned identifier against the physical device before using it.
Device commands accept required `--device-identifier`. Commands that support
`--devices-file` reject a target not present in that explicitly supplied local
inventory. Resolution always requires a current structured observation; cached
OS records are not substituted for live selection.

An inventory retains labels followed by identifiers:

```yaml
lab-device:
  - AA:BB:CC:DD:EE:FF
```

`devices.yaml` and `test_devices.yaml` are ignored. Do not include either file
in logs, fixtures, or support requests.

## Commands

| Command | Purpose |
| --- | --- |
| `polar-ble discover` | List nearby BLE advertisements. |
| `polar-ble prepare` | Verify readiness or perform one bounded preparation and persistent reconnect check. |
| `polar-ble connect` | Probe PMD/PFTP readiness, report, and disconnect. |
| `polar-ble raw` | List, collect, and safely clean raw `.REC` files. |
| `polar-ble passive` | List and collect passive `.BPB` files without schemas. |
| `polar-ble bpb` | Decode local BPB files through the verified schema cache. |
| `polar-ble ftu` | Validate or apply device-specific FTU data and inspect setup state. |
| `polar-ble sdk` | Explicitly manage local SDK source and generated schemas. |
| `polar-ble rec` | Check or invoke the local structured REC decoder. |
| `polar-ble doctor` | Report core and optional-schema readiness without mutation. |

Use `polar-ble COMMAND --help` for command-specific arguments. Raw data defaults
to `.local/polar-ble-raw`; passive data defaults to
`.local/polar-ble-passive`.

The complete command/subcommand inventory is in the [CLI reference](cli-reference.md).

## Library entry points

```python
from datetime import date

from polar_ble_tools import (
    PassiveDomain,
    collect_passive_files,
    prepare_device,
    probe_device,
    scan_devices,
)

devices = await scan_devices(timeout=15.0, name_substring="Polar")
target = devices[0].identifier  # Select deliberately.
preparation = await prepare_device(target)
assert preparation.readiness_verified and not preparation.final_connected
probe = await probe_device(target)
assert probe.readiness_verified and not probe.final_connected

passive = await collect_passive_files(
    target,
    domains=(PassiveDomain.DAILY_SUMMARY,),
    from_date=date(2026, 7, 1),
    to_date=date(2026, 7, 1),
    root=".local/polar-ble-passive",
)
```

The package does not read an inventory unless the caller supplies its path.

The facade also exposes structured local readiness and the live FTU workflow
without constructing CLI argument lists:

```python
from polar_ble_tools import apply_ftu, doctor, ftu_status
from polar_ble_tools.polar.setup import FtuProfile

readiness = doctor()
profile = FtuProfile.from_json_file("profile.json")
result = await apply_ftu("AA:BB:CC:DD:EE:FF", profile)
complete = await ftu_status("AA:BB:CC:DD:EE:FF")
```

`doctor()` is read-only and returns `DoctorReport`; its `to_dict()` is the same
shape used by `polar-ble doctor`. A top-level `warnings` list remains
non-fatal. When the active SDK and decoder commits differ, it reports both
commits and suggests `polar-ble sdk decoder build`; decoder availability is
unchanged. FTU helpers own the device session and expose apply, status, physical
configuration, settings read/update, and diagnostics. `load_ftu_profile()`
dispatches the Loop Gen 2 `FtuProfile` and Verity Sense
`VeritySenseFtuProfile`; `apply_ftu()` accepts either. The
[Verity Sense FTU sample](verity-sense-ftu-profile.example.json) causes
`apply_ftu()` to set current host system/local time after connecting and then
apply wear location. Runtime time is intentionally absent from the profile.
Unsupported pool-length input is rejected. See the complete
[Python API reference](python-api.md), including specialized SDK, BPB, REC,
passive-file, and lower-level protocol modules.

## REC decoder commands

`polar-ble sdk decoder build [--offline] [--no-activate]` builds the optional
sidecar. `verify`, `status`, `activate --commit SHA`, and `remove --commit SHA`
operate on a full lowercase commit SHA. `polar-ble rec status` is non-mutating;
`polar-ble rec decode INPUT --output OUTPUT` defaults to a 120-second deadline.
SDK, decoder, workspaces, and the shared JDK are stored under the platform user
data cache. Local corpus tests use `POLAR_BLE_REC_FIXTURE_MANIFEST`.
