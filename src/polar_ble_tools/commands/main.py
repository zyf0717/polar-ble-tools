from __future__ import annotations

import argparse
import sys

from polar_ble_tools import __version__


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="polar-ble",
        description="Unofficial local BLE tooling for supported Polar devices.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    subcommands = parser.add_subparsers(dest="command", title="commands")
    subcommands.add_parser("pair", help="Pair a device via BlueZ.")
    subcommands.add_parser("connect", help="Connect a paired device via BlueZ.")
    subcommands.add_parser("discover", help="List nearby BLE advertisements.")
    subcommands.add_parser("sdk", help="Manage the explicit local Polar SDK cache.")
    subcommands.add_parser("ftu", help="Validate or apply first-time-use setup.")
    subcommands.add_parser("raw", help="List, retrieve, and safely clean raw REC files.")
    subcommands.add_parser("passive", help="List and collect raw passive BPB files.")
    subcommands.add_parser("bpb", help="Decode local BPB files with the explicit schema cache.")
    subcommands.add_parser("rec", help="Decode local REC files with the optional SDK sidecar.")
    subcommands.add_parser("doctor", help="Report core and optional schema readiness.")
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "sdk":
        from polar_ble_tools.sdk_tools.cli import main as sdk_main

        return sdk_main(argv[1:])
    if argv and argv[0] == "ftu":
        from polar_ble_tools.commands.ftu import ftu_main

        return ftu_main(argv[1:])
    if argv and argv[0] == "raw":
        from polar_ble_tools.commands.raw import raw_main

        return raw_main(argv[1:])
    if argv and argv[0] == "passive":
        from polar_ble_tools.commands.passive import passive_main

        return passive_main(argv[1:])
    if argv and argv[0] == "doctor":
        from polar_ble_tools.commands.doctor import doctor_main

        return doctor_main(argv[1:])
    if argv and argv[0] == "bpb":
        from polar_ble_tools.commands.bpb import bpb_main

        return bpb_main(argv[1:])
    if argv and argv[0] == "rec":
        from polar_ble_tools.commands.rec import rec_main

        return rec_main(argv[1:])
    if argv and argv[0] == "discover":
        from polar_ble_tools.commands.discover import discover_main

        return discover_main(argv[1:])
    if argv and argv[0] == "pair":
        from polar_ble_tools.ble.bluetoothctl_pairing import pair_main

        return pair_main(argv[1:])
    if argv and argv[0] == "connect":
        from polar_ble_tools.ble.bluetoothctl_pairing import connect_main

        return connect_main(argv[1:])
    parser = _build_parser()
    if argv:
        parser.parse_args(argv)
        return 0
    parser.print_help()
    return 0
