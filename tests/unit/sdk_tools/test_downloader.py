from __future__ import annotations

import json
from pathlib import Path

import pytest

from polar_ble_tools.schemas.cache import SdkCache
from polar_ble_tools.sdk_tools.cli import main as sdk_main
from polar_ble_tools.sdk_tools.decoder import DecoderBuildResult
from polar_ble_tools.sdk_tools.discovery import ProtoDiscoveryError
from polar_ble_tools.sdk_tools.downloader import (
    PINNED_SDK_COMMIT,
    SdkDownloadError,
    SdkInstallResult,
    active_sdk_source,
    install_sdk,
    remove_all_sdk_cache,
    remove_sdk,
    sdk_status,
)
from polar_ble_tools.sdk_tools.generator import SchemaGenerationError
from polar_ble_tools.sdk_tools.proto_reader import ProtoReaderError
from polar_ble_tools.sdk_tools.verifier import SchemaVerificationError


def _make_sdk_source(tmp_path: Path) -> Path:
    source = tmp_path / "sdk-source"
    source.mkdir()
    (source / "README.md").write_text("user supplied SDK\n", encoding="utf-8")
    return source


def _write_staged_sdk(cache: SdkCache, revision: str) -> Path:
    root = cache.sdk_path(revision)
    source = root / "source"
    source.mkdir(parents=True)
    (root / "download-manifest.json").write_text(
        json.dumps({"resolved_commit": revision}), encoding="utf-8"
    )
    return source


def test_user_sdk_path_is_staged_as_supplied_and_can_be_removed(tmp_path: Path) -> None:
    source = _make_sdk_source(tmp_path)
    (source / "README.md").write_text("dirty is accepted\n", encoding="utf-8")
    (source / "user.proto").write_text('syntax = "proto3";\n', encoding="utf-8")
    cache = SdkCache(tmp_path / "cache")

    result = install_sdk(sdk_path=source, cache=cache)

    assert len(result.resolved_commit) == 40
    assert result.support_tier == "override"
    assert result.reused is False
    assert (result.source_path / "README.md").read_text(encoding="utf-8") == "dirty is accepted\n"
    assert (result.source_path / "user.proto").is_file()
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["source_type"] == "user_path"
    assert manifest["requested_ref"] == str(source.resolve())
    assert manifest["resolved_commit"] == result.resolved_commit
    assert manifest["source_content_sha256"].startswith(result.resolved_commit)
    assert manifest["format_version"] == 4
    assert "license_acceptance" not in manifest
    assert manifest["supported_commit"] == PINNED_SDK_COMMIT
    assert manifest["support_tier"] == "override"
    assert sdk_status(cache=cache).active_commit == result.resolved_commit

    assert install_sdk(sdk_path=source, cache=cache).reused is True
    assert remove_sdk(result.resolved_commit, cache=cache) is True
    assert sdk_status(cache=cache).active_commit is None


def test_local_source_does_not_require_a_licence_file(tmp_path: Path) -> None:
    source = tmp_path / "source-without-licence"
    source.mkdir()

    result = install_sdk(sdk_path=source, cache=SdkCache(tmp_path / "cache"))

    assert result.source_path.is_dir()


def test_reinstall_discards_legacy_acceptance_state(tmp_path: Path) -> None:
    source = _make_sdk_source(tmp_path)
    (source / "Polar_SDK_License.txt").write_text("upstream licence\n", encoding="utf-8")
    cache = SdkCache(tmp_path / "cache")
    installed = install_sdk(sdk_path=source, cache=cache)
    manifest = json.loads(installed.manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "format_version": 5,
            "license_acceptance": {"method": "cli_flag"},
            "license_notice_present": True,
        }
    )
    installed.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    legacy_copies = (
        installed.manifest_path.parent / "Polar_SDK_License.txt",
        cache.generated_path(installed.resolved_commit) / "Polar_SDK_License.txt",
    )
    for path in legacy_copies:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("legacy package copy\n", encoding="utf-8")

    reused = install_sdk(sdk_path=source, cache=cache)

    migrated = json.loads(reused.manifest_path.read_text(encoding="utf-8"))
    assert reused.reused
    assert migrated["format_version"] == 4
    assert "license_acceptance" not in migrated
    assert "license_notice_present" not in migrated
    assert all(not path.exists() for path in legacy_copies)
    assert (reused.source_path / "Polar_SDK_License.txt").is_file()


def test_local_source_rejects_symlinked_content(tmp_path: Path) -> None:
    source = _make_sdk_source(tmp_path)
    outside = tmp_path / "outside"
    outside.write_text("private\n", encoding="utf-8")
    (source / "linked").symlink_to(outside)

    with pytest.raises(SdkDownloadError, match="symbolic link"):
        install_sdk(sdk_path=source, cache=SdkCache(tmp_path / "cache"))


def test_local_source_rejects_remote_ref(tmp_path: Path) -> None:
    with pytest.raises(SdkDownloadError, match="either an official --ref or --sdk-path"):
        install_sdk(
            ref="preview",
            sdk_path=_make_sdk_source(tmp_path),
            cache=SdkCache(tmp_path / "cache"),
        )


def test_local_source_change_uses_a_new_cache_revision(tmp_path: Path) -> None:
    source = _make_sdk_source(tmp_path)
    cache = SdkCache(tmp_path / "cache")

    first = install_sdk(sdk_path=source, cache=cache)
    (source / "README.md").write_text("changed local SDK\n", encoding="utf-8")
    second = install_sdk(sdk_path=source, cache=cache)

    assert first.resolved_commit != second.resolved_commit
    assert sdk_status(cache=cache).installed_commits == tuple(
        sorted((first.resolved_commit, second.resolved_commit))
    )


def test_official_install_defaults_to_supported_commit_and_marks_override(
    monkeypatch, tmp_path: Path
) -> None:
    import polar_ble_tools.sdk_tools.downloader as downloader

    checkouts: list[str] = []

    def fake_git(*args: str, cwd: Path | None = None) -> str:
        if args[0] == "clone":
            source = Path(args[-1])
            source.mkdir()
            return ""
        if args[0] == "checkout":
            checkouts.append(args[-1])
            return ""
        if args[0] == "rev-parse":
            return PINNED_SDK_COMMIT if checkouts[-1] == PINNED_SDK_COMMIT else "e" * 40
        raise AssertionError(args)

    monkeypatch.setattr(downloader, "_run_git", fake_git)
    cache = SdkCache(tmp_path / "cache")

    pinned = install_sdk(cache=cache)
    override = install_sdk(ref="preview", cache=cache)

    assert checkouts == [PINNED_SDK_COMMIT, "preview"]
    assert pinned.support_tier == "pinned"
    pinned_manifest = json.loads(pinned.manifest_path.read_text(encoding="utf-8"))
    assert pinned_manifest["requested_ref"] == PINNED_SDK_COMMIT
    assert pinned_manifest["resolved_commit"] == PINNED_SDK_COMMIT
    assert pinned_manifest["supported_commit"] == PINNED_SDK_COMMIT
    assert pinned_manifest["source_type"] == "official"
    assert pinned_manifest["support_tier"] == "pinned"
    assert not (pinned.source_path / ".git").exists()
    assert override.resolved_commit == "e" * 40
    assert override.support_tier == "override"


def test_cli_install_declines_by_default(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("builtins.input", lambda: "")

    def unexpected_install(**_kwargs: object) -> object:
        raise AssertionError("installation must not start")

    monkeypatch.setattr("polar_ble_tools.sdk_tools.cli.install_sdk", unexpected_install)

    assert sdk_main(["install"]) == 1
    assert "Continue? [y/N]" in capsys.readouterr().err


def test_cli_requests_fresh_consent_when_reusing_an_sdk(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    responses = iter(("yes", "yes"))
    prompts = 0

    def confirm() -> str:
        nonlocal prompts
        prompts += 1
        return next(responses)

    result = SdkInstallResult(
        "candidate",
        "c" * 40,
        "user-supplied",
        tmp_path / "source",
        tmp_path / "manifest",
        True,
        "override",
    )
    monkeypatch.setattr("builtins.input", confirm)
    monkeypatch.setattr("polar_ble_tools.sdk_tools.cli.install_sdk", lambda **_kwargs: result)

    assert sdk_main(["download"]) == 0
    assert sdk_main(["download"]) == 0
    assert prompts == 2


def test_cli_decoder_build_warns_against_apache_only_redistribution(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    result = DecoderBuildResult("c" * 40, tmp_path / "decoder", True)
    monkeypatch.setattr("polar_ble_tools.sdk_tools.cli.build_decoder", lambda **_kwargs: result)

    assert sdk_main(["decoder", "build"]) == 0

    captured = capsys.readouterr()
    assert "built REC decoder" in captured.out
    assert "do not redistribute" in captured.err
    assert "Apache-2.0 licence alone" in captured.err


def test_cli_install_proceeds_when_confirmed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import polar_ble_tools.sdk_tools.cli as cli

    monkeypatch.setattr("builtins.input", lambda: "yes")
    result = SdkInstallResult(
        "candidate",
        "c" * 40,
        "user-supplied",
        tmp_path / "source",
        tmp_path / "manifest",
        False,
        "override",
    )
    monkeypatch.setattr(cli, "install_sdk", lambda **_kwargs: result)
    monkeypatch.setattr(cli, "inspect_sdk", lambda **_kwargs: object())
    monkeypatch.setattr(cli, "generate_schemas", lambda **_kwargs: object())
    monkeypatch.setattr(cli, "verify_schemas", lambda **_kwargs: tmp_path / "generated")
    monkeypatch.setattr(cli, "activate_sdk", lambda _revision: None)

    assert sdk_main(["install"]) == 0


def test_cli_warns_for_an_explicit_unsupported_override(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    from polar_ble_tools.sdk_tools.downloader import SdkInstallResult

    monkeypatch.setattr(
        "builtins.input", lambda: (_ for _ in ()).throw(AssertionError("-y must skip the prompt"))
    )
    monkeypatch.setattr(
        "polar_ble_tools.sdk_tools.cli.install_sdk",
        lambda **_kwargs: SdkInstallResult(
            "override",
            "d" * 40,
            "user-supplied",
            tmp_path / "source",
            tmp_path / "manifest",
            False,
            "override",
        ),
    )

    assert sdk_main(["download", "--ref", "override", "-y"]) == 0
    assert "warning: SDK revision" in capsys.readouterr().err


def test_cli_rejects_combining_remote_ref_and_local_path(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc_info:
        sdk_main(
            [
                "download",
                "-y",
                "--ref",
                "preview",
                "--sdk-path",
                str(_make_sdk_source(tmp_path)),
            ]
        )

    assert exc_info.value.code == 2


@pytest.mark.parametrize(
    ("failed_stage", "error_type"),
    [
        ("inspect_sdk", SdkDownloadError),
        ("inspect_sdk", ProtoDiscoveryError),
        ("inspect_sdk", ProtoReaderError),
        ("generate_schemas", SchemaGenerationError),
        ("verify_schemas", SchemaVerificationError),
    ],
)
def test_cli_install_failure_preserves_previously_active_revision(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    failed_stage: str,
    error_type: type[Exception],
) -> None:
    import polar_ble_tools.sdk_tools.cli as cli

    cache = SdkCache(tmp_path / "cache")
    active_revision, candidate_revision = "a" * 40, "b" * 40
    active_source = _write_staged_sdk(cache, active_revision)
    candidate_source = _write_staged_sdk(cache, candidate_revision)
    cache.active_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    cache.active_manifest_path.write_text(
        json.dumps({"resolved_commit": active_revision}), encoding="utf-8"
    )
    candidate = SdkInstallResult(
        "candidate",
        candidate_revision,
        "user-supplied",
        candidate_source,
        cache.sdk_path(candidate_revision) / "download-manifest.json",
        False,
        "override",
    )
    monkeypatch.setattr(cli.SdkCache, "default", classmethod(lambda _cls: cache))
    monkeypatch.setattr(cli, "install_sdk", lambda **kwargs: candidate)
    monkeypatch.setattr(cli, "inspect_sdk", lambda **kwargs: object())
    monkeypatch.setattr(cli, "generate_schemas", lambda **kwargs: object())
    monkeypatch.setattr(cli, "verify_schemas", lambda **kwargs: object())
    activations: list[str] = []
    monkeypatch.setattr(cli, "activate_sdk", lambda revision: activations.append(revision))

    def fail_stage(**_kwargs: object) -> object:
        raise error_type(f"{failed_stage} failed")

    monkeypatch.setattr(cli, failed_stage, fail_stage)

    with pytest.raises(SystemExit) as exc_info:
        sdk_main(["install", "-y"])

    assert exc_info.value.code == 2
    stderr = capsys.readouterr().err
    assert "Traceback" not in stderr
    assert 'pip install "polar-ble-tools[sdk]"' in stderr
    assert "polar-ble sdk install" in stderr
    assert activations == []
    assert sdk_status(cache=cache).active_commit == active_revision
    assert active_sdk_source(cache=cache) == (active_revision, active_source)


@pytest.mark.parametrize(
    ("command", "target", "error"),
    [
        ("inspect", "inspect_active_sdk", ProtoReaderError("grpcio-tools is unavailable")),
        (
            "generate",
            "generate_active_schemas",
            SchemaGenerationError("grpcio-tools is unavailable"),
        ),
        ("inspect", "inspect_active_sdk", ProtoDiscoveryError("Ambiguous protobuf layout")),
    ],
)
def test_cli_normalizes_schema_setup_failures_without_traceback(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: str,
    target: str,
    error: Exception,
) -> None:
    import polar_ble_tools.sdk_tools.cli as cli

    def fail() -> object:
        raise error

    monkeypatch.setattr(cli, target, fail)
    with pytest.raises(SystemExit) as exc_info:
        sdk_main([command])

    assert exc_info.value.code == 2
    stderr = capsys.readouterr().err
    assert "Traceback" not in stderr
    assert 'pip install "polar-ble-tools[sdk]"' in stderr
    assert "polar-ble sdk install" in stderr


def test_cli_install_activates_only_after_all_stages_succeed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import polar_ble_tools.sdk_tools.cli as cli

    cache = SdkCache(tmp_path / "cache")
    candidate_revision = "c" * 40
    candidate_source = _write_staged_sdk(cache, candidate_revision)
    candidate = SdkInstallResult(
        "candidate",
        candidate_revision,
        "user-supplied",
        candidate_source,
        cache.sdk_path(candidate_revision) / "download-manifest.json",
        False,
        "override",
    )
    monkeypatch.setattr(cli.SdkCache, "default", classmethod(lambda _cls: cache))
    monkeypatch.setattr(cli, "install_sdk", lambda **kwargs: candidate)
    events: list[str] = []

    def completed_stage(name: str):
        return lambda **_kwargs: events.append(name)

    for stage in ("inspect_sdk", "generate_schemas", "verify_schemas"):
        monkeypatch.setattr(cli, stage, completed_stage(stage))
    real_activate = cli.activate_sdk

    def activate(revision: str) -> None:
        events.append("activate")
        real_activate(revision, cache=cache)

    monkeypatch.setattr(cli, "activate_sdk", activate)

    assert sdk_main(["install", "-y"]) == 0
    assert events == ["inspect_sdk", "generate_schemas", "verify_schemas", "activate"]
    assert sdk_status(cache=cache).active_commit == candidate_revision


def test_remove_all_sdk_cache_removes_sdk_generated_and_active_state(tmp_path: Path) -> None:
    cache = SdkCache(tmp_path / "cache")
    cache.sdk_path(PINNED_SDK_COMMIT).mkdir(parents=True)
    cache.generated_path(PINNED_SDK_COMMIT).mkdir(parents=True)
    cache.active_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    cache.active_manifest_path.write_text('{"resolved_commit": "' + PINNED_SDK_COMMIT + '"}\n')

    assert remove_all_sdk_cache(cache=cache) is True
    assert not cache.sdk_root.exists()
    assert not cache.generated_root.exists()
    assert not cache.active_manifest_path.exists()


def test_remove_all_cli_dispatches_explicit_cleanup(monkeypatch, capsys) -> None:
    monkeypatch.setattr("polar_ble_tools.sdk_tools.cli.remove_all_sdk_cache", lambda: True)

    assert sdk_main(["remove", "--all"]) == 0
    assert "removed all Polar SDK and generated-schema cache entries" in capsys.readouterr().out
