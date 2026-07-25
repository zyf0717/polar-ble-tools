from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from polar_ble_tools.polar.offline import (
    DeviceDeletionResult,
    parse_offline_recording_path,
)
from polar_ble_tools.raw_data.storage import RawRecordingStore, RawRecordingStoreError


def _entry():
    return parse_offline_recording_path("/U/0/20260725/R/112233/ACC0.REC", size=10)


def test_store_writes_record_and_manifest_atomically(tmp_path: Path) -> None:
    store = RawRecordingStore(tmp_path / ".local" / "raw")

    manifest_entry = store.persist_record(
        "AA:BB:CC:DD:EE:FF",
        _entry(),
        b"raw-record",
        fetched_at=datetime(2026, 7, 25, tzinfo=UTC),
    )

    local_path = store.resolve_local_path(manifest_entry.local_path)
    assert local_path.read_bytes() == b"raw-record"
    assert manifest_entry.device_id == "AABBCCDDEEFF"
    assert manifest_entry.fetched_at == "2026-07-25T00:00:00Z"
    assert store.read_manifest("AA:BB:CC:DD:EE:FF") == [manifest_entry]
    assert store.verify_existing_record("AA:BB:CC:DD:EE:FF", _entry()) == manifest_entry
    assert not list(local_path.parent.glob(".*.tmp"))


def test_store_rejects_size_mismatch_without_writing(tmp_path: Path) -> None:
    store = RawRecordingStore(tmp_path / ".local" / "raw")

    with pytest.raises(RawRecordingStoreError, match="does not match"):
        store.persist_record("AA:BB:CC:DD:EE:FF", _entry(), b"short")

    assert not store.manifest_path("AA:BB:CC:DD:EE:FF").exists()


def test_store_hash_verification_rejects_modified_record(tmp_path: Path) -> None:
    store = RawRecordingStore(tmp_path / ".local" / "raw")
    manifest_entry = store.persist_record("AA:BB:CC:DD:EE:FF", _entry(), b"raw-record")

    store.resolve_local_path(manifest_entry.local_path).write_bytes(b"RAW-record")

    assert store.verify_existing_record("AA:BB:CC:DD:EE:FF", _entry()) is None
    assert store.has_existing_record("AA:BB:CC:DD:EE:FF", _entry()) is None


def test_store_writes_an_atomic_deletion_audit_row(tmp_path: Path) -> None:
    store = RawRecordingStore(tmp_path / ".local" / "raw")
    result = DeviceDeletionResult(
        device_path="/U/0/20260725/R/112233/ACC0.REC",
        record_type="ACC0",
        base_record_type="ACC",
        status="deleted",
        deleted_paths=["/U/0/20260725/R/112233/ACC0.REC"],
        cleaned_directories=["/U/0/20260725/R/112233/"],
    )

    store.append_deletion_result(
        "AA:BB:CC:DD:EE:FF",
        result,
        deleted_at=datetime(2026, 7, 25, tzinfo=UTC),
    )

    audit_path = store.deletion_audit_path("AA:BB:CC:DD:EE:FF")
    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    assert payload["device_id"] == "AABBCCDDEEFF"
    assert payload["deleted_at"] == "2026-07-25T00:00:00Z"
    assert payload["status"] == "deleted"
