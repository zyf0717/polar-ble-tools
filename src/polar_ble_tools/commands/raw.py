from __future__ import annotations

import argparse
import asyncio
import sys

from polar_ble_tools.collection import (
    cleanup_raw_recordings,
    collect_raw_recordings,
    list_raw_recordings,
)
from polar_ble_tools.commands.common import print_json, validate_authorized_device
from polar_ble_tools.raw_data.storage import DEFAULT_RAW_ROOT


def build_raw_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="List, retrieve, and safely clean raw REC files.")
    parser.add_argument("--mac-address", required=True)
    parser.add_argument(
        "--devices-file",
        help="Optional development YAML inventory used to restrict the target.",
    )
    parser.add_argument(
        "--root", default=str(DEFAULT_RAW_ROOT), help="Ignored local raw-data root."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", help="List device REC files without retrieving them.")
    collect = subparsers.add_parser(
        "collect", help="Fetch REC files into the local manifest store."
    )
    collect.add_argument("--type", action="append", dest="record_types")
    collect.add_argument("--delete-after-collect", action="store_true")
    cleanup = subparsers.add_parser("cleanup", help="Delete only hash-verified local copies.")
    selector = cleanup.add_mutually_exclusive_group(required=True)
    selector.add_argument("--type", action="append", dest="record_types")
    selector.add_argument("--all", action="store_true", dest="delete_all")
    cleanup.add_argument("--dry-run", action="store_true")
    return parser


async def _list_raw(args: argparse.Namespace) -> int:
    entries = await list_raw_recordings(args.mac_address)
    print_json(
        {
            "listed": len(entries),
            "records": [
                {
                    "path": entry.path,
                    "record_type": entry.record_type,
                    "size": entry.size,
                    "started_at": entry.started_at.isoformat() if entry.started_at else None,
                }
                for entry in entries
            ],
        }
    )
    return 0


async def _collect_raw(args: argparse.Namespace) -> int:
    result = await collect_raw_recordings(
        args.mac_address,
        root=args.root,
        record_types=set(args.record_types) if args.record_types else None,
        delete_after_collect=args.delete_after_collect,
    )
    print_json(result.to_jsonable())
    return 0 if result.ok else 1


async def _cleanup_raw(args: argparse.Namespace) -> int:
    result = await cleanup_raw_recordings(
        args.mac_address,
        root=args.root,
        record_types=set(args.record_types) if args.record_types else None,
        delete_all=args.delete_all,
        dry_run=args.dry_run,
    )
    print_json(result.to_jsonable())
    return 0 if result.ok else 1


def raw_main(argv: list[str] | None = None) -> int:
    args = build_raw_parser().parse_args(argv)
    error = validate_authorized_device(args)
    if error is not None:
        return error
    try:
        if args.command == "list":
            return asyncio.run(_list_raw(args))
        if args.command == "collect":
            return asyncio.run(_collect_raw(args))
        if args.command == "cleanup":
            return asyncio.run(_cleanup_raw(args))
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    raise AssertionError(f"Unsupported raw command: {args.command}")
