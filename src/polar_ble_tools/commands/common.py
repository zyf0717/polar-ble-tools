from __future__ import annotations

import json
import sys
from datetime import date

from polar_ble_tools.inventory import InventoryError, load_allowed_mac_addresses


def print_json(value: object) -> None:
    print(json.dumps(value, sort_keys=True))


def parse_cli_date(raw: str, field_name: str) -> date:
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"--{field_name} must use YYYY-MM-DD.") from exc


def validate_authorized_device(args: object) -> int | None:
    mac_address = getattr(args, "mac_address", None)
    devices_file = getattr(args, "devices_file", None)
    if mac_address is None:
        print("--mac-address is required for BLE commands.", file=sys.stderr)
        return 2
    if devices_file is None:
        return None
    try:
        allowed = load_allowed_mac_addresses(devices_file)
    except InventoryError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if mac_address.upper() not in allowed:
        print(
            f"Target device {mac_address.upper()} is not authorized in {devices_file}.",
            file=sys.stderr,
        )
        return 2
    return None
