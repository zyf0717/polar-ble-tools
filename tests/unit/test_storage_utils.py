from __future__ import annotations

import os
from types import SimpleNamespace

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

