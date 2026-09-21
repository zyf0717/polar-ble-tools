from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path

if os.name == "nt":
    import msvcrt as _file_locking
else:
    import fcntl as _file_locking


def _lock_descriptor(descriptor: int) -> None:
    if os.name == "nt":
        os.lseek(descriptor, 0, os.SEEK_SET)
        _file_locking.locking(descriptor, _file_locking.LK_LOCK, 1)
    else:
        _file_locking.flock(descriptor, _file_locking.LOCK_EX)


def _unlock_descriptor(descriptor: int) -> None:
    if os.name == "nt":
        os.lseek(descriptor, 0, os.SEEK_SET)
        _file_locking.locking(descriptor, _file_locking.LK_UNLCK, 1)
    else:
        _file_locking.flock(descriptor, _file_locking.LOCK_UN)


def _open_lock_descriptor(path: Path, descriptor: int) -> int:
    if os.name != "nt":
        return descriptor
    lock_path = path.with_name(f".{path.name}.lock")
    lock_descriptor = os.open(
        lock_path,
        os.O_RDWR
        | os.O_CREAT
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    if not stat.S_ISREG(os.fstat(lock_descriptor).st_mode):
        os.close(lock_descriptor)
        raise OSError(f"JSONL lock target is not a regular file: {lock_path}")
    return lock_descriptor


def sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    """Return a streaming SHA-256 digest without loading the file into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


def append_json_line(path: Path, value: dict[str, object]) -> None:
    line = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(
        path,
        os.O_RDWR
        | os.O_CREAT
        | os.O_APPEND
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    lock_descriptor = descriptor
    locked = False
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise OSError(f"JSONL target is not a regular file: {path}")
        lock_descriptor = _open_lock_descriptor(path, descriptor)
        _lock_descriptor(lock_descriptor)
        locked = True
        size = os.fstat(descriptor).st_size
        if size:
            os.lseek(descriptor, 0, os.SEEK_SET)
            existing = os.read(descriptor, size)
            if not existing.endswith(b"\n"):
                os.ftruncate(descriptor, existing.rfind(b"\n") + 1)
        written = 0
        while written < len(line):
            written += os.write(descriptor, line[written:])
        os.fsync(descriptor)
    finally:
        try:
            if locked:
                _unlock_descriptor(lock_descriptor)
        finally:
            try:
                if lock_descriptor != descriptor:
                    os.close(lock_descriptor)
            finally:
                os.close(descriptor)
