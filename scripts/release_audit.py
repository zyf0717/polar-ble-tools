#!/usr/bin/env python3
"""Fail closed on prohibited repository material without exposing its contents."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import PurePosixPath

PROHIBITED_SUFFIXES = (
    ".rec",
    ".bpb",
    ".proto",
    ".desc",
    ".pb",
    "_pb2.py",
    "_pb2.pyi",
    ".jar",
    ".aar",
    ".class",
    ".kt",
    ".swift",
    ".framework",
    ".xcframework",
    ".zip",
)
PROHIBITED_NAMES = frozenset(
    {"devices.yaml", "test_devices.yaml", "generated-manifest.json", "generation-plan.json"}
)
PRIVATE_COMPONENTS = frozenset({"captures", "credentials", "private", "profiles"})
PROJECT_OWNED_DECODER_TEMPLATES = frozenset(
    {
        "src/polar_ble_tools/sdk_tools/decoder_project/DecoderMain.kt",
        "src/polar_ble_tools/sdk_tools/decoder_project/build.gradle.kts",
        "src/polar_ble_tools/sdk_tools/decoder_project/settings.gradle.kts",
    }
)
SECRET_PATTERNS = (
    re.compile(rb"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----"),
    re.compile(rb"(?:ghp|github_pat)_[A-Za-z0-9_]{20,}"),
    re.compile(rb"AKIA[0-9A-Z]{16}"),
    re.compile(rb"(?:xox[baprs]|sk-[A-Za-z0-9])[A-Za-z0-9._-]{16,}"),
)
LOCAL_PATH_PATTERN = re.compile(b"(?:/" + b"home/|/" + b"Users/|[A-Za-z]:\\\\Users\\\\)")


def _git(*arguments: str, text: bool = True) -> str | bytes:
    completed = subprocess.run(["git", *arguments], check=True, capture_output=True, text=text)
    return completed.stdout


def _path_reason(path: str) -> str | None:
    parts = tuple(part.casefold() for part in PurePosixPath(path).parts)
    name = parts[-1] if parts else ""
    if path in PROJECT_OWNED_DECODER_TEMPLATES:
        return None
    if "polar-ble-sdk" in parts:
        return "sdk_checkout"
    if "_generated" in parts:
        return "generated_schema"
    if any(component in PRIVATE_COMPONENTS for component in parts):
        return "private_path"
    if name in PROHIBITED_NAMES:
        return "private_or_generated_name"
    if path.casefold().endswith(PROHIBITED_SUFFIXES):
        return "sdk_or_schema_artifact"
    return None


def _history_blob_ids() -> set[str]:
    output = _git("rev-list", "--objects", "--all")
    return {line.split(maxsplit=1)[0] for line in str(output).splitlines() if line}


def _audit_paths() -> dict[str, int]:
    violations: dict[str, int] = {}
    tree_paths = str(_git("ls-files")).splitlines()
    for path in tree_paths:
        if reason := _path_reason(path):
            violations[f"current:{reason}"] = violations.get(f"current:{reason}", 0) + 1
    for revision in str(_git("rev-list", "--all")).splitlines():
        names = _git("ls-tree", "-r", "--name-only", revision)
        for path in str(names).splitlines():
            if reason := _path_reason(path):
                key = f"history:{reason}"
                violations[key] = violations.get(key, 0) + 1
    return violations


def _audit_blob_contents() -> dict[str, int]:
    violations: dict[str, int] = {}
    for blob in _history_blob_ids():
        if _git("cat-file", "-t", blob).strip() != "blob":
            continue
        payload = _git("cat-file", "blob", blob, text=False)
        assert isinstance(payload, bytes)
        if any(pattern.search(payload) for pattern in SECRET_PATTERNS):
            violations["history:suspected_secret"] = (
                violations.get("history:suspected_secret", 0) + 1
            )
        if LOCAL_PATH_PATTERN.search(payload):
            violations["history:local_path"] = violations.get("history:local_path", 0) + 1
    return violations


def main() -> int:
    violations = _audit_paths()
    for category, count in _audit_blob_contents().items():
        violations[category] = violations.get(category, 0) + count
    summary = {
        "audit": "polar-ble-tools-release",
        "history_revisions": len(str(_git("rev-list", "--all")).splitlines()),
        "status": "failed" if violations else "passed",
        "violations": dict(sorted(violations.items())),
    }
    print(json.dumps(summary, sort_keys=True))
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
