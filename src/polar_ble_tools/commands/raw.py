from __future__ import annotations

import argparse
import asyncio
import sys

from polar_ble_tools.api import (
    available_recording_types,
    device_disk_space,
    fetch_raw_recording,
    offline_trigger,
    recording_settings,
    recording_status,
    start_recording,
    stop_recording,
    update_offline_trigger,
)
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
    subparsers.add_parser("types", help="List available offline recording types.")
    subparsers.add_parser("status", help="Show offline recording active status.")
    subparsers.add_parser("disk-space", help="Show device PFTP disk-space counters.")
    settings = subparsers.add_parser("settings", help="Show settings for one recording type.")
    settings.add_argument("--type", required=True)
    settings.add_argument("--full", action="store_true")
    start = subparsers.add_parser("start", help="Start one offline recording.")
    start.add_argument("--type", required=True)
    start.add_argument("--setting", action="append", default=[])
    stop = subparsers.add_parser("stop", help="Stop one offline recording.")
    stop.add_argument("--type", required=True)
    trigger = subparsers.add_parser("trigger", help="Read or update offline recording triggers.")
    trigger_subparsers = trigger.add_subparsers(dest="trigger_command", required=True)
    trigger_subparsers.add_parser("get", help="Show the current offline trigger configuration.")
    trigger_set = trigger_subparsers.add_parser(
        "set", help="Replace the offline trigger configuration."
    )
    trigger_set.add_argument(
        "--mode", required=True, choices=["disabled", "system-start", "exercise-start"]
    )
    trigger_set.add_argument("--type", action="append", default=[])
    trigger_set.add_argument("--setting", action="append", default=[])
    fetch = subparsers.add_parser("fetch", help="Fetch one raw REC file atomically.")
    fetch.add_argument("--path", required=True)
    fetch.add_argument("--output", required=True)
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


async def _types_raw(args: argparse.Namespace) -> int:
    print_json((await available_recording_types(args.mac_address)).to_jsonable())
    return 0


async def _status_raw(args: argparse.Namespace) -> int:
    print_json((await recording_status(args.mac_address)).to_jsonable())
    return 0


async def _settings_raw(args: argparse.Namespace) -> int:
    print_json(
        (await recording_settings(args.mac_address, args.type, full=args.full)).to_jsonable()
    )
    return 0


async def _start_raw(args: argparse.Namespace) -> int:
    print_json(
        (
            await start_recording(args.mac_address, args.type, _parse_settings(args.setting))
        ).to_jsonable()
    )
    return 0


async def _stop_raw(args: argparse.Namespace) -> int:
    print_json((await stop_recording(args.mac_address, args.type)).to_jsonable())
    return 0


async def _trigger_raw(args: argparse.Namespace) -> int:
    if args.trigger_command == "get":
        print_json((await offline_trigger(args.mac_address)).to_jsonable())
        return 0
    selected = _parse_settings(args.setting)
    trigger_features = {recording_type: selected for recording_type in args.type}
    print_json(
        (await update_offline_trigger(args.mac_address, args.mode, trigger_features)).to_jsonable()
    )
    return 0


async def _disk_space_raw(args: argparse.Namespace) -> int:
    print_json((await device_disk_space(args.mac_address)).to_jsonable())
    return 0


async def _fetch_raw(args: argparse.Namespace) -> int:
    print_json((await fetch_raw_recording(args.mac_address, args.path, args.output)).to_jsonable())
    return 0


def _parse_settings(raw_settings: list[str]) -> dict[str, int]:
    selected: dict[str, int] = {}
    normalized_keys: set[str] = set()
    for raw_setting in raw_settings:
        if "=" not in raw_setting:
            raise ValueError(f"Invalid setting {raw_setting!r}; expected KEY=VALUE.")
        raw_key, raw_value = raw_setting.split("=", 1)
        key = raw_key.strip().replace("-", "_").upper()
        if not key:
            raise ValueError(f"Invalid setting {raw_setting!r}; setting key is empty.")
        if key in normalized_keys:
            raise ValueError(f"Duplicate recording setting: {key}")
        try:
            value = int(raw_value, 0)
        except ValueError as exc:
            raise ValueError(f"Invalid integer setting value in {raw_setting!r}.") from exc
        normalized_keys.add(key)
        selected[key] = value
    return selected


def raw_main(argv: list[str] | None = None) -> int:
    args = build_raw_parser().parse_args(argv)
    error = validate_authorized_device(args)
    if error is not None:
        return error
    try:
        if args.command == "list":
            return asyncio.run(_list_raw(args))
        if args.command == "types":
            return asyncio.run(_types_raw(args))
        if args.command == "status":
            return asyncio.run(_status_raw(args))
        if args.command == "settings":
            return asyncio.run(_settings_raw(args))
        if args.command == "start":
            return asyncio.run(_start_raw(args))
        if args.command == "stop":
            return asyncio.run(_stop_raw(args))
        if args.command == "trigger":
            return asyncio.run(_trigger_raw(args))
        if args.command == "disk-space":
            return asyncio.run(_disk_space_raw(args))
        if args.command == "fetch":
            return asyncio.run(_fetch_raw(args))
        if args.command == "collect":
            return asyncio.run(_collect_raw(args))
        if args.command == "cleanup":
            return asyncio.run(_cleanup_raw(args))
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    raise AssertionError(f"Unsupported raw command: {args.command}")
