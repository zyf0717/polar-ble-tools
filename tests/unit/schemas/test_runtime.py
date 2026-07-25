from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

import pytest

from polar_ble_tools.schemas.cache import SdkCache
from polar_ble_tools.schemas.errors import SchemaUnavailableError
from polar_ble_tools.schemas.runtime import SchemaActivationManager, schema_activation_manager
from polar_ble_tools.sdk_tools.downloader import remove_sdk


def _manager_with_roots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[SchemaActivationManager, dict[str, Path], dict[str, str]]:
    commits = ("a" * 40, "b" * 40)
    cache = SdkCache(tmp_path / "cache")
    roots: dict[str, Path] = {}
    for commit, marker in zip(commits, ("a", "b"), strict=True):
        root = cache.generated_path(commit) / "python"
        root.mkdir(parents=True)
        (root / "switch_pb2.py").write_text(f"MARKER = {marker!r}\n", encoding="utf-8")
        roots[commit] = root
    active = {"commit": commits[0]}

    monkeypatch.setattr(
        "polar_ble_tools.schemas.runtime.verify_schemas",
        lambda *, cache: roots[active["commit"]],
    )
    monkeypatch.setattr(
        "polar_ble_tools.sdk_tools.downloader.active_sdk_source",
        lambda *, cache: (active["commit"], cache.sdk_path(active["commit"]) / "source"),
    )
    return schema_activation_manager(cache), roots, active


def test_activation_rejects_commit_switch_after_generated_module_load(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, _roots, active = _manager_with_roots(tmp_path, monkeypatch)
    sys.modules.pop("switch_pb2", None)
    try:
        loaded = manager.require("switch_pb2").switch_pb2
        assert loaded.MARKER == "a"
        assert manager.loaded_module_names == {"switch_pb2"}

        active["commit"] = "b" * 40
        with pytest.raises(SchemaUnavailableError, match="start a new process"):
            manager.require("switch_pb2")

        assert sys.modules["switch_pb2"] is loaded
        assert manager.active_commit == "a" * 40
    finally:
        sys.modules.pop("switch_pb2", None)


def test_activation_rejects_removal_of_loaded_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, _roots, _active = _manager_with_roots(tmp_path, monkeypatch)
    sys.modules.pop("switch_pb2", None)
    try:
        manager.require("switch_pb2")
        manager.cache.sdk_path("a" * 40).mkdir(parents=True)
        with pytest.raises(SchemaUnavailableError, match="Cannot remove"):
            manager.ensure_removable("a" * 40)
        with pytest.raises(SchemaUnavailableError, match="Cannot remove"):
            remove_sdk("a" * 40, cache=manager.cache)
        assert manager.cache.sdk_path("a" * 40).is_dir()
        manager.ensure_removable("b" * 40)
    finally:
        sys.modules.pop("switch_pb2", None)


def test_activation_normalizes_missing_and_outside_modules_to_schema_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, _roots, _active = _manager_with_roots(tmp_path, monkeypatch)

    with pytest.raises(SchemaUnavailableError, match="schemas are not installed or are invalid"):
        manager.require("missing_pb2")

    outside = ModuleType("outside_pb2")
    outside.__file__ = str(tmp_path / "outside_pb2.py")
    sys.modules["outside_pb2"] = outside
    try:
        with pytest.raises(SchemaUnavailableError, match="outside the active cache"):
            manager.require("outside_pb2")
    finally:
        sys.modules.pop("outside_pb2", None)


def test_activation_with_no_cache_is_schema_unavailable_and_does_not_create_one(
    tmp_path: Path,
) -> None:
    cache = SdkCache(tmp_path / "empty-cache")
    manager = SchemaActivationManager(cache)

    with pytest.raises(SchemaUnavailableError, match="schemas are not installed or are invalid"):
        manager.require("missing_pb2")

    assert not cache.root.exists()
