from __future__ import annotations

import re
import uuid
from pathlib import Path

MAC_ADDRESS_RE = re.compile(r"(?:[0-9A-F]{2}[:-]){5}[0-9A-F]{2}", re.IGNORECASE)


class InventoryError(ValueError):
    """Raised when an authorized device inventory is invalid."""


def normalize_identifier(identifier: str) -> str:
    value = identifier.strip()
    if not value:
        raise InventoryError("Device identifier is empty.")
    if MAC_ADDRESS_RE.fullmatch(value):
        return value.replace("-", ":").upper()
    try:
        parsed_uuid = uuid.UUID(value)
    except ValueError:
        return value
    return str(parsed_uuid)


def identifier_key(identifier: str) -> str:
    return normalize_identifier(identifier)


def load_allowed_identifiers(path: str | Path) -> set[str]:
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
                    allowed.add(normalize_identifier(line[4:]))
                except InventoryError as exc:
                    raise InventoryError(
                        f"Invalid device identifier {line[4:].strip()!r} "
                        f"in devices file at line {line_number}."
                    ) from exc
                continue
            raise InventoryError(
                f"Unsupported devices file format at line {line_number}: {raw_line.rstrip()}"
            )
    if not allowed:
        raise InventoryError(f"No allowed device identifiers were found in {path}.")
    return allowed


def require_authorized_identifier(identifier: str, path: str | Path | None) -> str:
    normalized = normalize_identifier(identifier)
    if path is None:
        return normalized
    allowed = load_allowed_identifiers(path)
    allowed_keys = {identifier_key(item) for item in allowed}
    if identifier_key(normalized) not in allowed_keys:
        raise InventoryError(f"Target device is not authorized in {path}.")
    return normalized
