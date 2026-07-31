from __future__ import annotations

import argparse
import asyncio
import sys

from polar_ble_tools.ble.operations import prepare_device, probe_device
from polar_ble_tools.ble.transport import DeviceLifecycleError
from polar_ble_tools.commands.common import print_json, validate_authorized_device


def _target_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--device-identifier", required=True)
    parser.add_argument(
        "--devices-file",
        help="Optional local inventory used to restrict the selected identifier.",
    )
    return parser


def build_prepare_parser() -> argparse.ArgumentParser:
    return _target_parser("Prepare one authorized Polar BLE device and end disconnected.")


def build_connect_parser() -> argparse.ArgumentParser:
    return _target_parser("Probe Polar PMD/PFTP readiness and end disconnected.")


async def _prepare(args: argparse.Namespace) -> int:
    result = await prepare_device(
        args.device_identifier,
        devices_file=args.devices_file,
    )
    print_json(result.to_jsonable())
    return 0


async def _connect(args: argparse.Namespace) -> int:
    result = await probe_device(
        args.device_identifier,
        devices_file=args.devices_file,
    )
    print_json(result.to_jsonable())
    return 0


def prepare_main(argv: list[str] | None = None) -> int:
    args = build_prepare_parser().parse_args(argv)
    if (exit_code := validate_authorized_device(args)) is not None:
        return exit_code
    try:
        return asyncio.run(_prepare(args))
    except DeviceLifecycleError as exc:
        print(str(exc), file=sys.stderr)
        return 2


def connect_main(argv: list[str] | None = None) -> int:
    args = build_connect_parser().parse_args(argv)
    if (exit_code := validate_authorized_device(args)) is not None:
        return exit_code
    try:
        return asyncio.run(_connect(args))
    except DeviceLifecycleError as exc:
        print(str(exc), file=sys.stderr)
        return 2
