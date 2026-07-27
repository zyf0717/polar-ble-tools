from __future__ import annotations

import json
import tarfile
from pathlib import Path

import pytest

from polar_ble_tools.rec import DecoderVerificationError, decoder_status
from polar_ble_tools.schemas.cache import SdkCache
from polar_ble_tools.sdk_tools.decoder import (
    DecoderBuildError,
    _promote_decoder_directory,
    _replace_incomplete_directory,
    _restore_decoder_directory,
    _safe_jdk_archive_member,
    _tool_entry_verified,
    _write_tool_entry_manifest,
    _write_workspace,
    activate_decoder,
    remove_decoder,
)
from polar_ble_tools.sdk_tools.decoder.toolchain import toolchain_descriptor


def test_workspace_contains_all_cohesive_sidecar_modules(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"

    _write_workspace(workspace, commit="a" * 40)

    source = workspace / "src" / "main" / "kotlin"
    assert {path.name for path in source.glob("*.kt")} == {
        "BuildInfo.kt",
        "DecoderMain.kt",
        "JsonProtocol.kt",
        "PayloadAdapter.kt",
        "Publication.kt",
        "RecordingDecoder.kt",
    }


def test_jdk_archive_allows_only_links_contained_by_its_root() -> None:
    safe = tarfile.TarInfo("jdk-21/legal/jdk.accessibility/LICENSE")
    safe.type = tarfile.SYMTYPE
    safe.linkname = "../java.base/LICENSE"

    assert _safe_jdk_archive_member(safe, "jdk-21")
    assert safe.name == "legal/jdk.accessibility/LICENSE"

    unsafe = tarfile.TarInfo("jdk-21/legal/LICENSE")
    unsafe.type = tarfile.SYMTYPE
    unsafe.linkname = "../../../outside"

    with pytest.raises(DecoderBuildError, match="unsafe link"):
        _safe_jdk_archive_member(unsafe, "jdk-21")


def test_toolchain_promotion_replaces_incomplete_regular_directory(tmp_path: Path) -> None:
    staged, target = tmp_path / "staged", tmp_path / "target"
    _entry(staged, "replacement")
    _entry(target, "interrupted")

    _replace_incomplete_directory(staged, target, description="JDK")

    assert (target / "marker").read_text(encoding="utf-8") == "replacement"
    assert not staged.exists()


@pytest.mark.parametrize("architecture", ["x86_64", "aarch64"])
def test_cached_tool_entry_is_bound_to_architecture_descriptor(
    tmp_path: Path, architecture: str
) -> None:
    descriptor = toolchain_descriptor("linux", architecture)
    root = tmp_path / architecture
    executable = root / descriptor.java_relative_path
    executable.parent.mkdir(parents=True)
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)

    _write_tool_entry_manifest(
        root,
        executable,
        descriptor,
        kind="jdk",
        archive_sha256=descriptor.jdk_sha256,
    )

    assert _tool_entry_verified(
        root,
        executable,
        descriptor,
        kind="jdk",
        archive_sha256=descriptor.jdk_sha256,
    )
    executable.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    assert not _tool_entry_verified(
        root,
        executable,
        descriptor,
        kind="jdk",
        archive_sha256=descriptor.jdk_sha256,
    )


def _entry(path: Path, marker: str) -> None:
    path.mkdir(parents=True)
    (path / "marker").write_text(marker, encoding="utf-8")


def test_decoder_promotion_can_restore_previous_entry(tmp_path: Path) -> None:
    root = tmp_path / "decoder"
    target, staged = root / "commit", root / ".staged"
    _entry(target, "previous")
    _entry(staged, "new")

    backup = _promote_decoder_directory(staged, target)

    assert backup is not None
    assert (target / "marker").read_text(encoding="utf-8") == "new"
    assert (backup / "marker").read_text(encoding="utf-8") == "previous"

    _restore_decoder_directory(target, backup)

    assert (target / "marker").read_text(encoding="utf-8") == "previous"
    assert not backup.exists()


def test_failed_activation_restores_previous_active_manifest(tmp_path: Path) -> None:
    cache = SdkCache(tmp_path / "cache")
    previous, invalid = "a" * 40, "b" * 40
    cache.active_decoder_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    cache.active_decoder_manifest_path.write_text(
        json.dumps({"sdk_commit": previous}), encoding="utf-8"
    )
    manifest = cache.decoder_path(invalid) / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("{}", encoding="utf-8")

    with pytest.raises(DecoderVerificationError):
        activate_decoder(invalid, cache=cache)

    assert json.loads(cache.active_decoder_manifest_path.read_text(encoding="utf-8")) == {
        "sdk_commit": previous
    }


def test_status_recovers_interrupted_same_commit_promotion(tmp_path: Path) -> None:
    cache = SdkCache(tmp_path / "cache")
    commit = "c" * 40
    target = cache.decoder_path(commit)
    backup = target.with_name(f".{commit}.previous-interrupted")
    _entry(backup, "previous")
    (backup / "manifest.json").write_text(
        json.dumps(
            {
                "manifest_version": 1,
                "decoder_protocol_version": 1,
                "sdk_commit": commit,
                "executable_relative_path": "bin/polar-rec-decoder",
                "executable_sha256": "0" * 64,
                "runtime_files": {},
                "verification_level": "handshake",
                "verified": True,
            }
        ),
        encoding="utf-8",
    )
    cache.active_decoder_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    cache.active_decoder_manifest_path.write_text(
        json.dumps({"sdk_commit": commit}), encoding="utf-8"
    )

    status = decoder_status(cache=cache)

    assert not status.available
    assert target.is_dir()
    assert not backup.exists()


@pytest.mark.parametrize(
    "commit",
    ["../../outside", "/absolute/path", "a" * 39, "A" * 40, "a" * 40 + ".tmp", "*" * 40],
)
def test_decoder_lifecycle_rejects_unsafe_commit_paths(tmp_path: Path, commit: str) -> None:
    cache = SdkCache(tmp_path / "cache")
    sentinel = tmp_path / "outside"
    sentinel.mkdir()
    marker = sentinel / "keep"
    marker.write_text("safe", encoding="utf-8")

    with pytest.raises(DecoderBuildError, match="full lowercase"):
        remove_decoder(commit, cache=cache)

    assert marker.read_text(encoding="utf-8") == "safe"


def test_status_rejects_malformed_active_commit(tmp_path: Path) -> None:
    cache = SdkCache(tmp_path / "cache")
    cache.active_decoder_manifest_path.parent.mkdir(parents=True)
    cache.active_decoder_manifest_path.write_text(
        json.dumps({"sdk_commit": "../../outside"}), encoding="utf-8"
    )

    status = decoder_status(cache=cache)

    assert not status.available
    assert "invalid SDK commit" in (status.reason or "")


def test_remove_decoder_also_removes_orphaned_workspace(tmp_path: Path) -> None:
    cache = SdkCache(tmp_path / "cache")
    commit = "d" * 40
    workspace = cache.decoder_build_path(commit)
    workspace.mkdir(parents=True)

    assert remove_decoder(commit, cache=cache)
    assert not workspace.exists()
