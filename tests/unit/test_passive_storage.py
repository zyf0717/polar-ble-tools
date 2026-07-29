from __future__ import annotations

import json
from pathlib import Path

import pytest

from polar_ble_tools.passive_data.storage import PassiveFileStore, PassiveFileStoreError


def test_persist_and_verify_passive_file(tmp_path: Path) -> None:
    store = PassiveFileStore(tmp_path)
    entry = store.persist_file(
        "AA:BB:CC:DD:EE:FF",
        domain="daily_summary",
        device_path="/U/0/20260625/DSUM/DSUM.BPB",
        device_size=3,
        payload=b"raw",
        logical_date="2026-06-25",
    )

    assert entry.local_path == "AABBCCDDEEFF/files/U/0/20260625/DSUM/DSUM.BPB"
    assert store.resolve_local_path(entry.local_path).read_bytes() == b"raw"
    assert (
        store.verify_existing_file(
            "AA:BB:CC:DD:EE:FF",
            device_path="/U/0/20260625/DSUM/DSUM.BPB",
            device_size=3,
        )
        == entry
    )


def test_passive_store_rejects_size_mismatch_and_escaping_path(tmp_path: Path) -> None:
    store = PassiveFileStore(tmp_path)
    with pytest.raises(PassiveFileStoreError, match="byte count"):
        store.persist_file(
            "AA:BB:CC:DD:EE:FF",
            domain="daily_summary",
            device_path="/U/0/20260625/DSUM/DSUM.BPB",
            device_size=4,
            payload=b"raw",
            logical_date="2026-06-25",
        )
    with pytest.raises(PassiveFileStoreError, match="Invalid passive device path"):
        store.local_file_path("AA:BB:CC:DD:EE:FF", "/U/../../escape.BPB")


def test_passive_store_rejects_symlinked_device_directory(tmp_path: Path) -> None:
    store = PassiveFileStore(tmp_path / "store")
    outside = tmp_path / "outside"
    outside.mkdir()
    store.root.mkdir()
    (store.root / "AABBCCDDEEFF").symlink_to(outside, target_is_directory=True)

    with pytest.raises(PassiveFileStoreError, match="contains a symlink"):
        store.persist_file(
            "AA:BB:CC:DD:EE:FF",
            domain="daily_summary",
            device_path="/U/0/20260625/DSUM/DSUM.BPB",
            device_size=3,
            payload=b"raw",
            logical_date="2026-06-25",
        )

    assert tuple(outside.iterdir()) == ()


def test_passive_store_writes_payload_free_deletion_audit(tmp_path: Path) -> None:
    store = PassiveFileStore(tmp_path)
    store.append_deletion_audit(
        "AA:BB:CC:DD:EE:FF",
        operation_id="operation-1",
        domain="daily_summary",
        logical_date="2026-06-25",
        device_path="/U/0/20260625/DSUM/DSUM.BPB",
        local_path="AABBCCDDEEFF/files/U/0/20260625/DSUM/DSUM.BPB",
        local_sha256="a" * 64,
        status="dry_run",
        dry_run=True,
    )

    row = json.loads(store.deletion_audit_path("AA:BB:CC:DD:EE:FF").read_text())
    assert row["status"] == "dry_run"
    assert row["dry_run"] is True
    assert set(row) >= {
        "observed_at",
        "operation_id",
        "schema_version",
        "device_id",
        "domain",
        "logical_date",
        "device_path",
        "local_path",
        "local_sha256",
        "status",
        "deleted_paths",
        "error",
        "dry_run",
    }
