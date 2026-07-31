from __future__ import annotations

import argparse
import asyncio
import sys

from polar_ble_tools.ble.operations import scan_devices
from polar_ble_tools.ble.transport import DeviceLifecycleError
from polar_ble_tools.commands.common import print_json


def build_discover_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read nearby BLE advertisements without pairing or connecting."
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="BLE scan timeout in seconds. Default: %(default)s",
    )
    parser.add_argument(
        "--name",
        help="Optional case-insensitive device-name substring filter.",
    )
    return parser


async def _discover(args: argparse.Namespace) -> int:
    devices = await scan_devices(timeout=args.timeout, name_substring=args.name)
    print_json(
        {
            "count": len(devices),
            "devices": [device.to_jsonable() for device in devices],
        }
    )
    return 0


def discover_main(argv: list[str] | None = None) -> int:
    args = build_discover_parser().parse_args(argv)
    try:
        return asyncio.run(_discover(args))
    except (DeviceLifecycleError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
