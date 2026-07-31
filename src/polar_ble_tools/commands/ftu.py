from __future__ import annotations

import argparse
import asyncio
import sys

from polar_ble_tools.api import (
    apply_ftu,
    diagnose_ftu,
    ftu_status,
    physical_configuration,
    update_user_device_settings,
    user_device_settings,
)
from polar_ble_tools.commands.common import (
    print_json as _print_json,
)
from polar_ble_tools.commands.common import (
    validate_authorized_device as _validate_authorized_device,
)
from polar_ble_tools.polar.setup import (
    DeviceLocation,
    SetupError,
    SetupValidationError,
    UserDeviceSettingsPatch,
    VeritySenseFtuProfile,
    load_ftu_profile,
)


def build_ftu_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Apply and inspect Polar first-time-use setup over BLE."
    )
    parser.add_argument(
        "--device-identifier",
        help="Target Polar BLE platform identifier.",
    )
    parser.add_argument(
        "--devices-file",
        help="Optional development YAML inventory used to restrict the target.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    dry_run = subparsers.add_parser("dry-run", help="Validate FTU profile offline.")
    dry_run.add_argument("--profile", required=True, help="FTU profile JSON file.")

    apply = subparsers.add_parser("apply", help="Apply FTU profile to the device.")
    apply.add_argument("--profile", required=True, help="FTU profile JSON file.")

    subparsers.add_parser("status", help="Report whether FTU is complete.")
    subparsers.add_parser("physical-config", help="Read physical setup data.")
    subparsers.add_parser("diagnose", help="Read setup diagnostic state.")

    settings = subparsers.add_parser("settings", help="Read or patch device settings.")
    settings_subparsers = settings.add_subparsers(
        dest="settings_command",
        required=True,
    )
    settings_subparsers.add_parser("get", help="Read user-device settings.")
    settings_set = settings_subparsers.add_parser(
        "set",
        help="Patch user-device settings.",
    )
    settings_set.add_argument("--device-location", help="Device location enum name.")
    settings_set.add_argument(
        "--usb-connection-mode",
        choices=["true", "false"],
        help="Enable or disable USB connection mode.",
    )
    settings_set.add_argument(
        "--automatic-training-detection-mode",
        choices=["true", "false"],
        help="Enable or disable automatic training detection.",
    )
    settings_set.add_argument(
        "--automatic-training-detection-sensitivity",
        type=int,
        help="Automatic training detection sensitivity, 0..100.",
    )
    settings_set.add_argument(
        "--minimum-training-duration-seconds",
        type=int,
        help="Minimum automatic training duration in seconds.",
    )
    settings_set.add_argument(
        "--autos-files",
        choices=["true", "false"],
        help="Enable or disable automatic OHR measurement files.",
    )
    return parser


async def _apply_ftu(args: argparse.Namespace) -> int:
    profile = load_ftu_profile(args.profile)
    result = await apply_ftu(args.device_identifier, profile)
    _print_json(
        {
            "ftu_applied": result.ftu_applied,
            "settings_updated": result.settings_updated,
        }
    )
    return 0


async def _status_ftu(args: argparse.Namespace) -> int:
    _print_json({"ftu_done": await ftu_status(args.device_identifier)})
    return 0


async def _physical_config_ftu(args: argparse.Namespace) -> int:
    config = await physical_configuration(args.device_identifier)
    _print_json(config.to_jsonable() if config is not None else None)
    return 0


async def _settings_get_ftu(args: argparse.Namespace) -> int:
    settings = await user_device_settings(args.device_identifier)
    _print_json(settings.to_jsonable())
    return 0


async def _settings_set_ftu(args: argparse.Namespace) -> int:
    patch = _settings_patch_from_args(args)
    await update_user_device_settings(args.device_identifier, patch)
    _print_json({"settings_updated": True})
    return 0


async def _diagnose_ftu(args: argparse.Namespace) -> int:
    _print_json(await diagnose_ftu(args.device_identifier))
    return 0


def _dry_run_ftu(args: argparse.Namespace) -> int:
    profile = load_ftu_profile(args.profile)
    settings_patch = profile.user_device_settings
    if isinstance(profile, VeritySenseFtuProfile):
        _print_json(
            {
                "valid": True,
                "profile": {
                    "path": args.profile,
                    "fields": ["device_family", "device_location"],
                },
                "operations": [
                    "SET_SYSTEM_TIME",
                    "SET_LOCAL_TIME",
                    "GET /U/0/S/UDEVSET.BPB",
                    "PUT /U/0/S/UDEVSET.BPB",
                ],
                "payload_sizes": "requires generated schemas",
            }
        )
        return 0
    operations = [
        "REQUEST_SYNCHRONIZATION",
        "INITIALIZE_SESSION",
        "START_SYNC",
        "SET_SYSTEM_TIME",
        "SET_LOCAL_TIME",
        "PUT /U/0/S/PHYSDATA.BPB",
        "PUT /U/0/USERID.BPB",
        "STOP_SYNC",
        "TERMINATE_SESSION",
    ]
    fields = [
        "gender",
        "birth_date",
        "height_cm",
        "weight_kg",
        "max_heart_rate_bpm",
        "resting_heart_rate_bpm",
        "vo2_max",
        "training_background",
        "typical_day",
        "sleep_goal_minutes",
        "device_time",
    ]
    profile_output: dict[str, object] = {
        "path": args.profile,
        "fields": fields,
    }
    if settings_patch is not None and settings_patch.has_changes:
        fields.append("user_device_settings")
        profile_output["user_device_settings_fields"] = _settings_patch_field_names(settings_patch)
        operations.extend(
            [
                "GET /U/0/S/UDEVSET.BPB",
                "PUT /U/0/S/UDEVSET.BPB",
            ]
        )
    _print_json(
        {
            "valid": True,
            "profile": profile_output,
            "operations": operations,
            # Dry-run is deliberately schema-free; encoding sizes are only
            # meaningful after an explicit SDK generation installation.
            "payload_sizes": "requires generated schemas",
        }
    )
    return 0


def _settings_patch_from_args(args: argparse.Namespace) -> UserDeviceSettingsPatch:
    return UserDeviceSettingsPatch(
        device_location=DeviceLocation.from_name(args.device_location)
        if args.device_location is not None
        else None,
        usb_connection_mode=_parse_bool(args.usb_connection_mode)
        if args.usb_connection_mode is not None
        else None,
        automatic_training_detection_mode=_parse_bool(args.automatic_training_detection_mode)
        if args.automatic_training_detection_mode is not None
        else None,
        automatic_training_detection_sensitivity=(args.automatic_training_detection_sensitivity),
        minimum_training_duration_seconds=args.minimum_training_duration_seconds,
        autos_files_enabled=_parse_bool(args.autos_files) if args.autos_files is not None else None,
    )


def _parse_bool(raw: str) -> bool:
    return raw == "true"


def _settings_patch_field_names(patch: UserDeviceSettingsPatch) -> list[str]:
    return [
        field_name
        for field_name in (
            "device_location",
            "usb_connection_mode",
            "automatic_training_detection_mode",
            "automatic_training_detection_sensitivity",
            "minimum_training_duration_seconds",
            "autos_files_enabled",
        )
        if getattr(patch, field_name) is not None
    ]


def ftu_main(argv: list[str] | None = None) -> int:
    parser = build_ftu_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "dry-run":
            return _dry_run_ftu(args)

        authorization_error = _validate_authorized_device(args)
        if authorization_error is not None:
            return authorization_error

        if args.command == "apply":
            return asyncio.run(_apply_ftu(args))
        if args.command == "status":
            return asyncio.run(_status_ftu(args))
        if args.command == "physical-config":
            return asyncio.run(_physical_config_ftu(args))
        if args.command == "diagnose":
            return asyncio.run(_diagnose_ftu(args))
        if args.command == "settings" and args.settings_command == "get":
            return asyncio.run(_settings_get_ftu(args))
        if args.command == "settings" and args.settings_command == "set":
            return asyncio.run(_settings_set_ftu(args))
    except SetupValidationError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except SetupError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    parser.error(f"Unsupported command: {args.command}")
    return 2
