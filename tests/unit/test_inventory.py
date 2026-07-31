from pathlib import Path

import pytest

from polar_ble_tools.inventory import (
    InventoryError,
    load_allowed_identifiers,
    normalize_identifier,
    require_authorized_identifier,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (" aa-bb-cc-dd-ee-ff ", "AA:BB:CC:DD:EE:FF"),
        ("550E8400-E29B-41D4-A716-446655440000", "550e8400-e29b-41d4-a716-446655440000"),
        ("opaque Platform Key", "opaque Platform Key"),
    ],
)
def test_identifier_normalization(raw: str, expected: str) -> None:
    assert normalize_identifier(raw) == expected


def test_inventory_accepts_platform_neutral_identifiers(tmp_path: Path) -> None:
    inventory = tmp_path / "devices.yaml"
    inventory.write_text(
        "lab:\n"
        "  - aa-bb-cc-dd-ee-ff\n"
        "  - 550E8400-E29B-41D4-A716-446655440000\n"
        "  - opaque Platform Key\n",
        encoding="utf-8",
    )

    assert load_allowed_identifiers(inventory) == {
        "AA:BB:CC:DD:EE:FF",
        "550e8400-e29b-41d4-a716-446655440000",
        "opaque Platform Key",
    }
    assert (
        require_authorized_identifier("550e8400-e29b-41d4-a716-446655440000", inventory)
        == "550e8400-e29b-41d4-a716-446655440000"
    )


def test_inventory_rejects_unauthorized_identifier_without_disclosing_entries(
    tmp_path: Path,
) -> None:
    inventory = tmp_path / "devices.yaml"
    inventory.write_text("lab:\n  - AA:BB:CC:DD:EE:FF\n", encoding="utf-8")

    with pytest.raises(InventoryError) as captured:
        require_authorized_identifier("11:22:33:44:55:66", inventory)
    assert "11:22:33:44:55:66" not in str(captured.value)
    assert "AA:BB:CC:DD:EE:FF" not in str(captured.value)


def test_opaque_identifiers_remain_case_sensitive(tmp_path: Path) -> None:
    inventory = tmp_path / "devices.yaml"
    inventory.write_text("lab:\n  - Opaque-ID\n", encoding="utf-8")

    with pytest.raises(InventoryError):
        require_authorized_identifier("opaque-id", inventory)
