from __future__ import annotations

import json
import sys
from datetime import date

from polar_ble_tools.inventory import InventoryError, require_authorized_identifier


def print_json(value: object) -> None:
    print(json.dumps(value, sort_keys=True))


def parse_cli_date(raw: str, field_name: str) -> date:
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"--{field_name} must use YYYY-MM-DD.") from exc


def validate_authorized_device(args: object) -> int | None:
    identifier = getattr(args, "device_identifier", None)
    devices_file = getattr(args, "devices_file", None)
    if identifier is None:
        print("--device-identifier is required for BLE commands.", file=sys.stderr)
        return 2
    try:
        normalized = require_authorized_identifier(identifier, devices_file)
    except InventoryError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    args.device_identifier = normalized
    return None
