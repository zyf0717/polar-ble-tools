# Device setup

BlueZ pairing and Polar first-time-use (FTU) are separate operations. Pair and
verify the device before FTU. FTU writes device files and requires locally
generated schemas; it is not a pairing fallback.

## Pair and verify

Remove other active host connections, put the device into its pairing window,
and use its exact address:

```bash
polar-ble discover --scan-seconds 15 --name Polar
bluetoothctl remove AA:BB:CC:DD:EE:FF
polar-ble pair --mac-address AA:BB:CC:DD:EE:FF --scan-seconds 15
bluetoothctl info AA:BB:CC:DD:EE:FF
```

Proceed only when BlueZ reports `Paired: yes`, `Bonded: yes`, and
`Trusted: yes`, followed by `Ready for other actions: yes`. `Connected` is
transient and is `no` after a successful pairing.

## Prepare FTU

Create the local schema cache. Proceeding at the prompt accepts the Polar BLE
SDK licence:

```bash
python -m pip install "polar-ble-tools[sdk]"
polar-ble sdk install
```

Copy [the profile example](ftu-profile.example.json) to a private location and
replace every value. Profiles contain personal physical data and must not be
committed or placed in shared logs.

Validate without BLE activity:

```bash
polar-ble ftu dry-run --profile ~/.config/polar-ble-tools/ftu-profile.json
```

Apply and inspect setup:

```bash
polar-ble ftu --mac-address AA:BB:CC:DD:EE:FF apply \
  --profile ~/.config/polar-ble-tools/ftu-profile.json
polar-ble ftu --mac-address AA:BB:CC:DD:EE:FF status
polar-ble ftu --mac-address AA:BB:CC:DD:EE:FF diagnose
```

`polar-ble pair` releases its temporary BlueZ connection after it verifies the
bond. FTU therefore opens and closes only its own async BLE session.

If application is interrupted, reconnect and inspect `status` and `diagnose`
before deciding whether to apply the same reviewed profile again. Avoid
`physical-config` in shared terminals because it reads personal setup data.
