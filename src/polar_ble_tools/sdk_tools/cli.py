from __future__ import annotations

import argparse
import subprocess
import sys
from json import JSONDecodeError
from pathlib import Path

from polar_ble_tools.schemas.cache import SdkCache
from polar_ble_tools.sdk_tools.discovery import ProtoDiscoveryError
from polar_ble_tools.sdk_tools.downloader import (
    SdkDownloadError,
    activate_sdk,
    install_sdk,
    remove_all_sdk_cache,
    remove_sdk,
    sdk_status,
)
from polar_ble_tools.sdk_tools.generator import (
    SchemaGenerationError,
    generate_active_schemas,
    generate_schemas,
)
from polar_ble_tools.sdk_tools.inspection import inspect_active_sdk, inspect_sdk
from polar_ble_tools.sdk_tools.proto_reader import ProtoReaderError
from polar_ble_tools.sdk_tools.verifier import (
    SchemaVerificationError,
    verify_active_schemas,
    verify_schemas,
)

_SCHEMA_SETUP_REMEDIATION = (
    "Schema-backed setup and BPB features require:\n"
    '  pip install "polar-ble-tools[sdk]"\n'
    "  polar-ble sdk install --accept-license"
)


def _add_install_arguments(parser: argparse.ArgumentParser) -> None:
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--ref",
        help="Official SDK tag or commit; defaults to this release's supported SDK pin.",
    )
    source.add_argument(
        "--sdk-path",
        type=Path,
        help="Local SDK source; staged as an unsupported content-addressed override.",
    )
    parser.add_argument(
        "--accept-license", action="store_true", help="Confirm acceptance of Polar's SDK licence."
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="polar-ble sdk", description="Manage the local Polar SDK cache."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("download", "install"):
        _add_install_arguments(commands.add_parser(command))
    commands.add_parser("status")
    commands.add_parser("inspect")
    commands.add_parser("generate")
    commands.add_parser("verify")
    remove = commands.add_parser("remove")
    removal_target = remove.add_mutually_exclusive_group(required=True)
    removal_target.add_argument("--commit", help="Full resolved SDK revision identifier.")
    removal_target.add_argument(
        "--all",
        action="store_true",
        help="Remove every cached SDK revision and generated schema artifact.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "download":
            result = install_sdk(
                accept_license=args.accept_license,
                ref=args.ref,
                sdk_path=args.sdk_path,
            )
            _warn_unsupported_override(result)
            state = "reused" if result.reused else "installed"
            print(f"{state} Polar SDK {result.resolved_commit} at {result.source_path}")
            return 0
        if args.command == "install":
            # Keep the current activation untouched until every stage has
            # completed.  The staged revision is safe to retain for diagnosis.
            result = install_sdk(
                accept_license=args.accept_license,
                ref=args.ref,
                sdk_path=args.sdk_path,
                activate=False,
            )
            _warn_unsupported_override(result)
            inspect_sdk(
                resolved_commit=result.resolved_commit,
                source=result.source_path,
                cache=SdkCache.default(),
            )
            generate_schemas(
                resolved_commit=result.resolved_commit,
                source=result.source_path,
                cache=SdkCache.default(),
            )
            verified = verify_schemas(commit=result.resolved_commit, cache=SdkCache.default())
            activate_sdk(result.resolved_commit)
            print(
                f"installed Polar SDK {result.resolved_commit}; verified generated cache: {verified}"
            )
            return 0
        if args.command == "status":
            status = sdk_status()
            print(f"active: {status.active_commit or 'none'}")
            print("installed:")
            for commit in status.installed_commits:
                print(f"  {commit}")
            return 0
        if args.command == "inspect":
            result = inspect_active_sdk()
            print(f"inspected Polar SDK {result.resolved_commit}: {result.report_path}")
            return 0
        if args.command == "generate":
            result = generate_active_schemas()
            print(f"generated schemas for {result.resolved_commit}: {result.python_path}")
            return 0
        if args.command == "verify":
            print(f"verified schemas: {verify_active_schemas()}")
            return 0
        if args.command == "remove":
            if args.all:
                if remove_all_sdk_cache():
                    print("removed all Polar SDK and generated-schema cache entries")
                    return 0
                print("Polar SDK cache is already empty")
                return 1
            if remove_sdk(args.commit):
                print(f"removed Polar SDK {args.commit} and generated schemas")
                return 0
            print(f"Polar SDK {args.commit} is not installed")
            return 1
    except (
        SdkDownloadError,
        ProtoDiscoveryError,
        ProtoReaderError,
        SchemaGenerationError,
        SchemaVerificationError,
        JSONDecodeError,
        OSError,
        subprocess.SubprocessError,
        ValueError,
    ) as exc:
        parser.error(f"SDK setup failed: {exc}\n{_SCHEMA_SETUP_REMEDIATION}")
    raise AssertionError(f"Unhandled SDK command: {args.command}")


def _warn_unsupported_override(result) -> None:
    if result.support_tier == "override":
        print(
            "warning: SDK revision "
            f"{result.resolved_commit} differs from this release's supported pin; "
            "the source revision is recorded, but schema compatibility and "
            "device behavior are unsupported.",
            file=sys.stderr,
        )
