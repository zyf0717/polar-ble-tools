from __future__ import annotations

import argparse
import json
import sys

from polar_ble_tools.ble.bluetoothctl_pairing import discover_devices


def build_discover_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read nearby BLE advertisements without pairing or connecting."
    )
    parser.add_argument(
        "--scan-seconds",
        type=float,
        default=10.0,
        help="BLE scan duration. Default: %(default)s",
    )
    parser.add_argument(
        "--name",
        help="Optional case-insensitive device-name substring filter.",
    )
    parser.add_argument(
        "--bluetoothctl",
        default="bluetoothctl",
        help="Path to the bluetoothctl executable. Default: %(default)s",
    )
    return parser


def discover_main(argv: list[str] | None = None) -> int:
    args = build_discover_parser().parse_args(argv)
    try:
        devices = discover_devices(
            scan_seconds=args.scan_seconds,
            name_substring=args.name,
            executable=args.bluetoothctl,
        )
    except FileNotFoundError as exc:
        print(f"bluetoothctl is not installed or not on PATH: {exc}", file=sys.stderr)
        return 1
    except (ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "discovered": len(devices),
                "devices": [
                    {
                        "mac_address": device.mac_address,
                        "name": device.name,
                        "rssi": device.rssi,
                    }
                    for device in devices
                ],
            },
            sort_keys=True,
        )
    )
    return 0
