from __future__ import annotations

import re
from pathlib import Path

MAC_ADDRESS_RE = re.compile(r"(?:[0-9A-F]{2}:){5}[0-9A-F]{2}", re.IGNORECASE)


class InventoryError(ValueError):
    """Raised when the authorized device inventory is invalid."""


def normalize_mac_address(mac_address: str) -> str:
    normalized = mac_address.strip().upper()
    if not MAC_ADDRESS_RE.fullmatch(normalized):
        raise InventoryError(f"Invalid MAC address: {mac_address}")
    return normalized


def load_allowed_mac_addresses(path: str | Path) -> set[str]:
    allowed: set[str] = set()
    current_section: str | None = None
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.split("#", 1)[0].rstrip()
            if not line.strip():
                continue
            if line.lstrip() == line and line.endswith(":"):
                current_section = line[:-1].strip()
                if not current_section:
                    raise InventoryError(
                        f"Invalid empty section name in devices file at line {line_number}."
                    )
                continue
            if line.startswith("  - "):
                if current_section is None:
                    raise InventoryError(
                        f"Device entry appears before any section in devices file at line {line_number}."
                    )
                try:
                    allowed.add(normalize_mac_address(line[4:]))
                except InventoryError as exc:
                    raise InventoryError(
                        f"Invalid MAC address {line[4:].strip()!r} in devices file at line {line_number}."
                    ) from exc
                continue
            raise InventoryError(
                f"Unsupported devices file format at line {line_number}: {raw_line.rstrip()}"
            )
    if not allowed:
        raise InventoryError(f"No allowed MAC addresses were found in {path}.")
    return allowed
