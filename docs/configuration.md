# Configuration and command line

All device operations select an explicit MAC address or platform identifier.
Keep device inventories, profiles, captures, and credentials outside version
control.

## Discovery and authorization

Discovery does not pair, connect, trust, or otherwise alter a device:

```bash
polar-ble discover --scan-seconds 15 --name Polar
```

Confirm the returned identifier against the physical device before using it.
Pairing and connection accept `--mac-address`. Commands that support
`--devices-file` reject a target not present in that explicitly supplied local
inventory.

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
| `polar-ble pair` | Pair, bond, trust, and best-effort connect through BlueZ. |
| `polar-ble connect` | Connect a previously paired and trusted device. |
| `polar-ble raw` | List, collect, and safely clean raw `.REC` files. |
| `polar-ble passive` | List and collect passive `.BPB` files without schemas. |
| `polar-ble bpb` | Decode local BPB files through the verified schema cache. |
| `polar-ble ftu` | Validate or apply FTU data and inspect setup state. |
| `polar-ble sdk` | Explicitly manage local SDK source and generated schemas. |
| `polar-ble rec` | Check or invoke the local structured REC decoder. |
| `polar-ble doctor` | Report core and optional-schema readiness without mutation. |

Use `polar-ble COMMAND --help` for command-specific arguments. Raw data defaults
to `.local/polar-ble-raw`; passive data defaults to
`.local/polar-ble-passive`.

## Library entry points

```python
from polar_ble_tools import (
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
```

The package does not read an inventory unless the caller supplies its path.

## REC decoder commands

`polar-ble sdk decoder build [--offline] [--no-activate]` builds the optional
sidecar. `verify`, `status`, `activate --commit SHA`, and `remove --commit SHA`
operate on a full lowercase commit SHA. `polar-ble rec status` is non-mutating;
`polar-ble rec decode INPUT --output OUTPUT` defaults to a 120-second deadline.
SDK, decoder, workspaces, and the shared JDK are stored under the platform user
data cache. Local corpus tests use `POLAR_BLE_REC_FIXTURE_MANIFEST`.
