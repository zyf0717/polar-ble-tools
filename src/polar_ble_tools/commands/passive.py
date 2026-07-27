from __future__ import annotations

import argparse
import asyncio
import sys

from polar_ble_tools.collection import collect_passive_files, list_passive_files
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
    parser.add_argument("--from-date", required=True, help="First logical date, YYYY-MM-DD.")
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
    return parser


def _domains(raw: list[str] | None) -> tuple[PassiveDomain, ...]:
    return tuple(normalize_passive_domain(value) for value in raw) if raw else PASSIVE_DOMAIN_ORDER


def _dates(args: argparse.Namespace):
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
    result = await collect_passive_files(
        args.mac_address,
        domains=domains,
        from_date=from_date,
        to_date=to_date,
        root=args.root,
        existing_file_policy=args.existing_file_policy,
    )
    print_json(result.to_jsonable())
    return 0 if result.ok else 1


def passive_main(argv: list[str] | None = None) -> int:
    args = build_passive_parser().parse_args(argv)
    authorization_error = validate_authorized_device(args)
    if authorization_error is not None:
        return authorization_error
    try:
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
