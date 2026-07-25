from __future__ import annotations

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
