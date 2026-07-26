"""Validation for content-addressed SDK revision identifiers."""

from __future__ import annotations

import re
from pathlib import Path

_COMMIT_RE = re.compile(r"[0-9a-f]{40}")


def require_full_commit(value: str) -> str:
    """Return a safe full SDK commit identifier or reject it."""
    if not isinstance(value, str) or not _COMMIT_RE.fullmatch(value):
        raise ValueError("Decoder operations require a full lowercase 40-character SDK commit SHA.")
    return value


def require_within(path: Path, root: Path) -> Path:
    """Resolve *path* and prove it remains beneath the resolved cache *root*."""
    resolved_path = path.resolve()
    try:
        resolved_path.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"Decoder cache path escapes its root: {path}") from exc
    return resolved_path
