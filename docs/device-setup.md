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

## Prepare Loop Gen 2 FTU

Create the local schema cache. Proceeding at the prompt accepts the Polar BLE
SDK licence:

```bash
python -m pip install "polar-ble-tools[sdk]"
polar-ble sdk install
```

Copy the [Loop Gen 2 profile example](loop-gen2-ftu-profile.example.json) to a
private location and replace every value. Profiles contain personal physical
data and must not be committed or placed in shared logs.

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

## Prepare Verity Sense FTU

The [Verity Sense profile example](verity-sense-ftu-profile.example.json)
contains the supported wear-location setting:

```json
{
  "device_family": "POLAR_VERITY_SENSE",
  "device_location": "UPPER_ARM_LEFT"
}
```

Validate and apply it with the same commands:

```bash
polar-ble ftu dry-run \
  --profile ~/.config/polar-ble-tools/verity-sense-ftu-profile.json
polar-ble ftu --mac-address AA:BB:CC:DD:EE:FF apply \
  --profile ~/.config/polar-ble-tools/verity-sense-ftu-profile.json
```

Verity application reads, patches, and writes `UDEVSET.BPB` through Bleak. It
does not execute Loop physical-data or user-identifier writes. Pool length is
not supported and is rejected during profile validation. Do not add missing
Loop demographic fields or pass the Loop profile to Verity Sense.
