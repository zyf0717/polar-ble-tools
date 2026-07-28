from __future__ import annotations

import json
from pathlib import Path

import pytest

from polar_ble_tools.schemas.cache import SdkCache
from polar_ble_tools.schemas.runtime import schema_activation_manager
from polar_ble_tools.sdk_tools.removal import (
    RemovalArtifactStatus,
    SdkRemovalError,
    remove_sdk_artifacts,
)


def _directory(path: Path) -> None:
    path.mkdir(parents=True)
    (path / "marker").write_text("local cache\n", encoding="utf-8")


def _activate(cache: SdkCache, *, sdk: str | None = None, decoder: str | None = None) -> None:
    cache.root.mkdir(parents=True, exist_ok=True)
    if sdk is not None:
        cache.active_manifest_path.write_text(
            json.dumps({"resolved_commit": sdk}), encoding="utf-8"
        )
    if decoder is not None:
        cache.active_decoder_manifest_path.write_text(
            json.dumps({"sdk_commit": decoder}), encoding="utf-8"
        )


def test_dry_run_retains_decoder_without_explicit_inclusion(tmp_path: Path) -> None:
    cache = SdkCache(tmp_path / "cache")
    commit = "a" * 40
    for path in (
        cache.sdk_path(commit),
        cache.generated_path(commit),
        cache.decoder_path(commit),
        cache.decoder_build_path(commit),
    ):
        _directory(path)
    _activate(cache, sdk=commit, decoder=commit)

    result = remove_sdk_artifacts((commit,), dry_run=True, cache=cache)

    assert result.dry_run
    assert result.records[0].sdk_source is RemovalArtifactStatus.WOULD_REMOVE
    assert result.records[0].generated_schemas is RemovalArtifactStatus.WOULD_REMOVE
    assert result.records[0].decoder_runtime is RemovalArtifactStatus.RETAINED
    assert result.records[0].decoder_workspace is RemovalArtifactStatus.RETAINED
    assert result.records[0].active_sdk
    assert result.records[0].active_decoder
    assert all(path.is_dir() for path in (cache.sdk_path(commit), cache.decoder_path(commit)))
    assert cache.active_manifest_path.is_file()
    assert cache.active_decoder_manifest_path.is_file()


def test_multiple_commit_removal_can_include_corresponding_decoders(tmp_path: Path) -> None:
    cache = SdkCache(tmp_path / "cache")
    commits = ("a" * 40, "b" * 40)
    for commit in commits:
        for path in (
            cache.sdk_path(commit),
            cache.generated_path(commit),
            cache.decoder_path(commit),
            cache.decoder_build_path(commit),
        ):
            _directory(path)
    _activate(cache, sdk=commits[0], decoder=commits[0])
    toolchain = cache.rec_jvm_toolchain_root / "shared"
    _directory(toolchain)

    result = remove_sdk_artifacts(commits, include_decoders=True, cache=cache)

    assert not result.dry_run
    assert all(
        record.decoder_runtime is RemovalArtifactStatus.REMOVED
        and record.decoder_workspace is RemovalArtifactStatus.REMOVED
        for record in result.records
    )
    for commit in commits:
        assert not cache.sdk_path(commit).exists()
        assert not cache.generated_path(commit).exists()
        assert not cache.decoder_path(commit).exists()
        assert not cache.decoder_build_path(commit).exists()
    assert not cache.active_manifest_path.exists()
    assert not cache.active_decoder_manifest_path.exists()
    assert toolchain.is_dir()


def test_remove_all_with_decoders_includes_decoder_only_commits(tmp_path: Path) -> None:
    cache = SdkCache(tmp_path / "cache")
    sdk_commit, decoder_commit = "a" * 40, "b" * 40
    _directory(cache.sdk_path(sdk_commit))
    _directory(cache.decoder_path(decoder_commit))
    _directory(cache.decoder_build_path(decoder_commit))

    result = remove_sdk_artifacts(remove_all=True, include_decoders=True, dry_run=True, cache=cache)

    assert tuple(record.commit for record in result.records) == (sdk_commit, decoder_commit)
    decoder = result.records[1]
    assert decoder.sdk_source is RemovalArtifactStatus.ABSENT
    assert decoder.decoder_runtime is RemovalArtifactStatus.WOULD_REMOVE


def test_preflight_rejects_unsafe_decoder_before_any_removal(tmp_path: Path) -> None:
    cache = SdkCache(tmp_path / "cache")
    safe_commit, unsafe_commit = "a" * 40, "b" * 40
    _directory(cache.sdk_path(safe_commit))
    outside = tmp_path / "outside"
    _directory(outside)
    cache.decoder_root.mkdir(parents=True)
    cache.decoder_path(unsafe_commit).symlink_to(outside, target_is_directory=True)

    with pytest.raises(SdkRemovalError, match="escapes its root"):
        remove_sdk_artifacts((safe_commit, unsafe_commit), include_decoders=True, cache=cache)

    assert cache.sdk_path(safe_commit).is_dir()
    assert (outside / "marker").is_file()


def test_loaded_schema_revision_blocks_bulk_removal_before_changes(tmp_path: Path) -> None:
    cache = SdkCache(tmp_path / "cache")
    commit = "a" * 40
    _directory(cache.sdk_path(commit))
    schema_activation_manager(cache).active_commit = commit

    with pytest.raises(SdkRemovalError, match="Cannot remove the active generated cache"):
        remove_sdk_artifacts(remove_all=True, cache=cache)

    assert cache.sdk_path(commit).is_dir()


def test_absent_exact_commit_is_idempotent_success(tmp_path: Path) -> None:
    result = remove_sdk_artifacts(("a" * 40,), cache=SdkCache(tmp_path / "cache"))

    record = result.records[0]
    assert record.sdk_source is RemovalArtifactStatus.ABSENT
    assert record.generated_schemas is RemovalArtifactStatus.ABSENT
    assert record.decoder_runtime is RemovalArtifactStatus.ABSENT
    assert record.decoder_workspace is RemovalArtifactStatus.ABSENT


def test_removal_can_retain_verified_format_3_schemas(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = SdkCache(tmp_path / "cache")
    commit = "a" * 40
    _directory(cache.sdk_path(commit))
    _directory(cache.generated_path(commit))
    (cache.sdk_path(commit) / "download-manifest.json").write_text(
        json.dumps({"resolved_commit": commit}), encoding="utf-8"
    )
    (cache.generated_path(commit) / "generated-manifest.json").write_text(
        json.dumps({"format_version": 3}), encoding="utf-8"
    )
    _activate(cache, sdk=commit)
    monkeypatch.setattr(
        "polar_ble_tools.sdk_tools.removal.verify_schemas", lambda **_kwargs: object()
    )
    monkeypatch.setattr(
        "polar_ble_tools.sdk_tools.verifier.verify_schemas", lambda **_kwargs: object()
    )
    monkeypatch.setattr(
        "polar_ble_tools.sdk_tools.verifier.activate_schemas",
        lambda revision, *, cache: cache.active_schema_manifest_path.write_text(
            json.dumps({"resolved_commit": revision}), encoding="utf-8"
        ),
    )

    result = remove_sdk_artifacts((commit,), retain_schemas=True, cache=cache)

    assert result.retain_schemas is True
    assert result.records[0].generated_schemas is RemovalArtifactStatus.RETAINED
    assert result.records[0].active_schemas is True
    assert not cache.sdk_path(commit).exists()
    assert cache.generated_path(commit).is_dir()
    assert not cache.active_manifest_path.exists()
    assert cache.active_schema_manifest_path.is_file()


def test_api_rejects_commits_combined_with_remove_all(tmp_path: Path) -> None:
    with pytest.raises(SdkRemovalError, match="not both"):
        remove_sdk_artifacts(("a" * 40,), remove_all=True, cache=SdkCache(tmp_path / "cache"))


@pytest.mark.parametrize("commit", ["short", "A" * 40, "../../outside"])
def test_removal_requires_full_lowercase_commit(tmp_path: Path, commit: str) -> None:
    with pytest.raises(SdkRemovalError, match="full lowercase"):
        remove_sdk_artifacts((commit,), cache=SdkCache(tmp_path / "cache"))
