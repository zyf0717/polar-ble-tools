from __future__ import annotations

import argparse
import asyncio
import sys

from polar_ble_tools.bpb_decode import BpbManifestError, decode_passive_manifest
from polar_ble_tools.collection import (
    cleanup_passive_files,
    collect_passive_files,
    list_passive_files,
)
from polar_ble_tools.commands.common import parse_cli_date, print_json, validate_authorized_device
from polar_ble_tools.passive_data.storage import DEFAULT_PASSIVE_ROOT
from polar_ble_tools.polar.passive import (
    PASSIVE_DOMAIN_ORDER,
    PassiveDomain,
    normalize_passive_domain,
)


def build_passive_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="List and collect raw passive BPB files without requiring schemas."
    )
    parser.add_argument("--mac-address", required=True)
    parser.add_argument(
        "--devices-file", help="Optional development YAML inventory used to restrict the target."
    )
    parser.add_argument(
        "--root", default=str(DEFAULT_PASSIVE_ROOT), help="Ignored local passive-data root."
    )
    parser.add_argument("--from-date", help="First logical date, YYYY-MM-DD.")
    parser.add_argument("--to-date", help="Last logical date, YYYY-MM-DD; defaults to --from-date.")
    parser.add_argument(
        "--domain",
        action="append",
        choices=[domain.value for domain in PASSIVE_DOMAIN_ORDER],
        help="Passive domain to include; defaults to all domains.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="List passive files without retrieving them.")
    collect = commands.add_parser("collect", help="Fetch and hash-store passive files.")
    collect.add_argument(
        "--existing-file-policy",
        choices=["skip", "overwrite"],
        default="skip",
        help="Reuse verified local files or refetch them. Default: %(default)s.",
    )
    collect.add_argument("--delete-after-collect", action="store_true")
    collect.add_argument(
        "--decode",
        action="store_true",
        help="Decode the persisted local manifest after raw collection completes.",
    )
    collect.add_argument(
        "--decoded-output-dir",
        help="Decoded JSON directory inside the passive store; requires --decode.",
    )
    cleanup = commands.add_parser("cleanup", help="Delete only verified passive files.")
    cleanup.add_argument(
        "--domain", required=True, choices=[domain.value for domain in PASSIVE_DOMAIN_ORDER]
    )
    cleanup.add_argument(
        "--delete-through", required=True, help="Inclusive logical-date cutoff, YYYY-MM-DD."
    )
    cleanup.add_argument("--dry-run", action="store_true")
    return parser


def _domains(raw: list[str] | None) -> tuple[PassiveDomain, ...]:
    return tuple(normalize_passive_domain(value) for value in raw) if raw else PASSIVE_DOMAIN_ORDER


def _dates(args: argparse.Namespace):
    if args.from_date is None:
        raise ValueError("--from-date is required for passive list and collect.")
    from_date = parse_cli_date(args.from_date, "from-date")
    to_date = parse_cli_date(args.to_date, "to-date") if args.to_date else from_date
    if from_date > to_date:
        raise ValueError("--from-date must be before or equal to --to-date.")
    return from_date, to_date


async def _list(
    args: argparse.Namespace, domains: tuple[PassiveDomain, ...], from_date, to_date
) -> int:
    listing = await list_passive_files(
        args.mac_address, domains=domains, from_date=from_date, to_date=to_date
    )
    print_json(
        {
            "listed": len(listing.entries),
            "missing": listing.missing,
            "records": [
                {
                    "domain": entry.domain.value,
                    "logical_date": entry.logical_date.isoformat() if entry.logical_date else None,
                    "path": entry.path,
                    "size": entry.size,
                }
                for entry in listing.entries
            ],
        }
    )
    return 0


async def _collect(
    args: argparse.Namespace, domains: tuple[PassiveDomain, ...], from_date, to_date
) -> int:
    if args.decoded_output_dir is not None and not args.decode:
        raise ValueError("--decoded-output-dir requires --decode.")
    result = await collect_passive_files(
        args.mac_address,
        domains=domains,
        from_date=from_date,
        to_date=to_date,
        root=args.root,
        existing_file_policy=args.existing_file_policy,
        delete_after_collect=args.delete_after_collect,
    )
    if not args.decode:
        print_json(result.to_jsonable())
        return 0 if result.ok else 1
    try:
        decoding = decode_passive_manifest(
            result.manifest_path,
            output_dir=args.decoded_output_dir,
        )
        decoding_payload: dict[str, object] = decoding.to_jsonable()
        decoding_ok = decoding.ok
    except (BpbManifestError, OSError, ValueError) as exc:
        decoding_payload = {"error": str(exc), "failed": 1}
        decoding_ok = False
    print_json(
        {
            "collection": result.to_jsonable(),
            "decoding": decoding_payload,
        }
    )
    return 0 if result.ok and decoding_ok else 1


async def _cleanup(args: argparse.Namespace) -> int:
    result = await cleanup_passive_files(
        args.mac_address,
        root=args.root,
        domain=args.domain,
        delete_through=parse_cli_date(args.delete_through, "delete-through"),
        dry_run=args.dry_run,
    )
    print_json(result.to_jsonable())
    return 0 if result.ok else 1


def passive_main(argv: list[str] | None = None) -> int:
    args = build_passive_parser().parse_args(argv)
    authorization_error = validate_authorized_device(args)
    if authorization_error is not None:
        return authorization_error
    try:
        if args.command == "cleanup":
            return asyncio.run(_cleanup(args))
        from_date, to_date = _dates(args)
        domains = _domains(args.domain)
        if args.command == "list":
            return asyncio.run(_list(args, domains, from_date, to_date))
        if args.command == "collect":
            return asyncio.run(_collect(args, domains, from_date, to_date))
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    raise AssertionError(f"Unsupported passive command: {args.command}")
