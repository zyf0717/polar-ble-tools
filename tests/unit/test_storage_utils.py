from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

from polar_ble_tools import storage_utils


def test_windows_descriptor_locking_uses_first_byte(tmp_path, monkeypatch) -> None:
    path = tmp_path / "manifest.jsonl"
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    calls: list[tuple[int, int, int]] = []
    locking = SimpleNamespace(
        LK_LOCK=1,
        LK_UNLCK=2,
        locking=lambda fd, mode, length: calls.append((fd, mode, length)),
    )
    try:
        os.lseek(descriptor, 7, os.SEEK_SET)
        monkeypatch.setattr(storage_utils.os, "name", "nt")
        monkeypatch.setattr(storage_utils, "_file_locking", locking)

        storage_utils._lock_descriptor(descriptor)
        storage_utils._unlock_descriptor(descriptor)
    finally:
        os.close(descriptor)

    assert calls == [
        (descriptor, locking.LK_LOCK, 1),
        (descriptor, locking.LK_UNLCK, 1),
    ]


def test_windows_append_locks_sibling_file(tmp_path, monkeypatch) -> None:
    path = tmp_path / "manifest.jsonl"
    path.write_text('{"existing":true}\n', encoding="utf-8")
    opened: dict[int, str] = {}
    locked: list[str] = []
    real_open = os.open

    def tracked_open(target, flags, mode=0o777):
        descriptor = real_open(target, flags, mode)
        opened[descriptor] = str(target)
        return descriptor

    def lock(descriptor: int) -> None:
        locked.append(opened[descriptor])
        assert path.read_text(encoding="utf-8") == '{"existing":true}\n'

    monkeypatch.setattr(storage_utils.os, "name", "nt")
    monkeypatch.setattr(storage_utils.os, "open", tracked_open)
    monkeypatch.setattr(storage_utils, "_lock_descriptor", lock)
    monkeypatch.setattr(storage_utils, "_unlock_descriptor", lambda _descriptor: None)

    storage_utils.append_json_line(path, {"next": True})

    assert locked == [str(tmp_path / ".manifest.jsonl.lock")]
    assert path.read_text(encoding="utf-8") == '{"existing":true}\n{"next":true}\n'


@pytest.mark.skipif(os.name != "nt", reason="requires native Windows file locking")
def test_windows_manifest_remains_readable_while_append_lock_is_held(tmp_path, monkeypatch) -> None:
    path = tmp_path / "manifest.jsonl"
    path.write_text('{"existing":true}\n', encoding="utf-8")
    lock_descriptor = storage_utils._lock_descriptor

    def lock_and_read(descriptor: int) -> None:
        lock_descriptor(descriptor)
        assert path.read_text(encoding="utf-8") == '{"existing":true}\n'

    monkeypatch.setattr(storage_utils, "_lock_descriptor", lock_and_read)

    storage_utils.append_json_line(path, {"next": True})

    assert path.read_text(encoding="utf-8") == '{"existing":true}\n{"next":true}\n'
