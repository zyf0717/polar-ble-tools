# Configuration and command line

All device operations select an explicit MAC address or platform identifier.
Keep device inventories, profiles, captures, and credentials outside version
control.

## Discovery and authorization

Discovery reports only live BLE scan observations; it does not pair, connect,
trust, or otherwise alter a device:

```bash
polar-ble discover --scan-seconds 15 --name Polar
```

Confirm the returned identifier against the physical device before using it.
Pairing and connection accept `--mac-address`. Commands that support
`--devices-file` reject a target not present in that explicitly supplied local
inventory.

Pairing always performs a live discovery scan. For an explicit MAC address
that BlueZ already reports as paired, bonded, and trusted, a missing live
observation falls back to that cached bond for direct connection verification.

An inventory uses labels followed by MAC addresses:

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
| `polar-ble pair` | Pair, bond, trust, verify a BlueZ connection, then disconnect. |
| `polar-ble connect` | Connect a previously paired and trusted device. |
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
    connect_device,
    discover_devices,
    pair_device,
    release_device_connection,
)

devices = discover_devices(name_substring="Polar")
target = devices[0].mac_address  # Select deliberately.
pairing = pair_device(mac_address=target, scan_seconds=15.0)
assert pairing.paired and pairing.bonded and pairing.trusted
connection = connect_device(mac_address=target)
release_device_connection(mac_address=target)

passive = await collect_passive_files(
    target,
    domains=(PassiveDomain.DAILY_SUMMARY,),
    from_date=date(2026, 7, 1),
    to_date=date(2026, 7, 1),
    root=".local/polar-ble-passive",
)
```

The package does not read an inventory unless the caller supplies its path.

The `0.4.0` facade also exposes structured local readiness and the live FTU
workflow without constructing CLI argument lists:

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
