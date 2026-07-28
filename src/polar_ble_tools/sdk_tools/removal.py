"""Guarded multi-revision removal for local SDK and decoder artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Iterable

from polar_ble_tools.schemas.cache import SdkCache
from polar_ble_tools.schemas.errors import SchemaUnavailableError
from polar_ble_tools.sdk_tools.downloader import remove_sdk
from polar_ble_tools.sdk_tools.generator import GENERATED_MANIFEST
from polar_ble_tools.sdk_tools.revisions import require_full_commit, require_within
from polar_ble_tools.sdk_tools.verifier import SchemaVerificationError, verify_schemas


class SdkRemovalError(RuntimeError):
    """The requested cache removal could not be planned safely."""


class RemovalArtifactStatus(StrEnum):
    ABSENT = "absent"
    RETAINED = "retained"
    WOULD_REMOVE = "would_remove"
    REMOVED = "removed"


@dataclass(frozen=True)
class SdkRemovalRecord:
    commit: str
    sdk_source: RemovalArtifactStatus
    generated_schemas: RemovalArtifactStatus
    decoder_runtime: RemovalArtifactStatus
    decoder_workspace: RemovalArtifactStatus
    active_sdk: bool
    active_decoder: bool
    active_schemas: bool = False

    def to_jsonable(self) -> dict[str, object]:
        return {
            "commit": self.commit,
            "sdk_source": self.sdk_source.value,
            "generated_schemas": self.generated_schemas.value,
            "decoder_runtime": self.decoder_runtime.value,
            "decoder_workspace": self.decoder_workspace.value,
            "active_sdk": self.active_sdk,
            "active_schemas": self.active_schemas,
            "active_decoder": self.active_decoder,
        }


@dataclass(frozen=True)
class SdkRemovalResult:
    dry_run: bool
    include_decoders: bool
    records: tuple[SdkRemovalRecord, ...]
    retain_schemas: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "records", tuple(self.records))

    def to_jsonable(self) -> dict[str, object]:
        return {
            "dry_run": self.dry_run,
            "include_decoders": self.include_decoders,
            "retain_schemas": self.retain_schemas,
            "records": [record.to_jsonable() for record in self.records],
        }


@dataclass(frozen=True)
class _RemovalTarget:
    commit: str
    sdk_source: bool
    generated_schemas: bool
    decoder_runtime: bool
    decoder_workspace: bool
    active_sdk: bool
    active_schemas: bool
    active_decoder: bool


def _full_commit(value: str) -> str:
    try:
        return require_full_commit(value)
    except ValueError as exc:
        raise SdkRemovalError(
            "SDK removal requires a full lowercase 40-character commit SHA."
        ) from exc


def _active_commit(path: Path, field: str) -> str | None:
    if not path.exists() and not path.is_symlink():
        return None
    if not path.is_file() or path.is_symlink():
        raise SdkRemovalError(f"Active cache manifest is missing or unsafe: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SdkRemovalError(f"Active cache manifest is invalid: {path}") from exc
    value = payload.get(field)
    if value is None:
        raise SdkRemovalError(f"Active cache manifest is missing {field}: {path}")
    return _full_commit(value)


def _directory_present(path: Path, root: Path) -> bool:
    try:
        require_within(path, root)
    except ValueError as exc:
        raise SdkRemovalError(str(exc)) from exc
    if not path.exists() and not path.is_symlink():
        return False
    if not path.is_dir() or path.is_symlink():
        raise SdkRemovalError(f"Cache target is not a regular directory: {path}")
    return True


def _cached_commits(root: Path) -> set[str]:
    if not root.exists() and not root.is_symlink():
        return set()
    if not root.is_dir() or root.is_symlink():
        raise SdkRemovalError(f"Cache root is not a regular directory: {root}")
    commits: set[str] = set()
    for path in root.iterdir():
        try:
            commit = require_full_commit(path.name)
        except ValueError:
            continue
        if not path.is_dir() or path.is_symlink():
            raise SdkRemovalError(f"Cache target is not a regular directory: {path}")
        commits.add(commit)
    return commits


def _targets(
    commits: Iterable[str],
    *,
    remove_all: bool,
    include_decoders: bool,
    retain_schemas: bool,
    cache: SdkCache,
) -> tuple[_RemovalTarget, ...]:
    commits = tuple(commits)
    if remove_all and commits:
        raise SdkRemovalError("Specify exact commits or --all, not both.")
    active_sdk = _active_commit(cache.active_manifest_path, "resolved_commit")
    active_schemas = _active_commit(cache.active_schema_manifest_path, "resolved_commit")
    if (
        active_schemas is None
        and active_sdk is not None
        and (cache.generated_path(active_sdk) / GENERATED_MANIFEST).is_file()
    ):
        active_schemas = active_sdk
    active_decoder = _active_commit(cache.active_decoder_manifest_path, "sdk_commit")
    if remove_all:
        selected = _cached_commits(cache.sdk_root)
        if not retain_schemas:
            selected |= _cached_commits(cache.generated_root)
        if active_sdk is not None:
            selected.add(active_sdk)
        if include_decoders:
            selected |= _cached_commits(cache.decoder_root)
            selected |= _cached_commits(cache.decoder_build_root)
            if active_decoder is not None:
                selected.add(active_decoder)
    else:
        selected = {_full_commit(commit) for commit in commits}
        if not selected:
            raise SdkRemovalError("Select at least one --commit or use --all.")
    from polar_ble_tools.schemas.runtime import schema_activation_manager

    if retain_schemas:
        for commit in sorted(selected):
            generated = cache.generated_path(commit)
            if not generated.is_dir():
                continue
            try:
                verify_schemas(commit=commit, cache=cache)
                manifest = json.loads((generated / GENERATED_MANIFEST).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, SchemaVerificationError) as exc:
                raise SdkRemovalError(
                    f"Cannot retain unverified schemas for {commit}: {exc}"
                ) from exc
            if manifest.get("format_version") != 3:
                raise SdkRemovalError(
                    "Retaining schemas while removing SDK source requires format-3 "
                    f"schemas for {commit}; regenerate them first."
                )
    else:
        manager = schema_activation_manager(cache)
        try:
            if remove_all:
                manager.ensure_removable(None)
            else:
                for commit in sorted(selected):
                    manager.ensure_removable(commit)
        except SchemaUnavailableError as exc:
            raise SdkRemovalError(str(exc)) from exc
    return tuple(
        _RemovalTarget(
            commit=commit,
            sdk_source=_directory_present(cache.sdk_path(commit), cache.sdk_root),
            generated_schemas=_directory_present(
                cache.generated_path(commit), cache.generated_root
            ),
            decoder_runtime=(
                _directory_present(cache.decoder_path(commit), cache.decoder_root)
                if include_decoders
                else cache.decoder_path(commit).exists() or cache.decoder_path(commit).is_symlink()
            ),
            decoder_workspace=(
                _directory_present(cache.decoder_build_path(commit), cache.decoder_build_root)
                if include_decoders
                else cache.decoder_build_path(commit).exists()
                or cache.decoder_build_path(commit).is_symlink()
            ),
            active_sdk=active_sdk == commit,
            active_schemas=active_schemas == commit,
            active_decoder=active_decoder == commit,
        )
        for commit in sorted(selected)
    )


def _artifact_status(present: bool, *, selected: bool, dry_run: bool) -> RemovalArtifactStatus:
    if not present:
        return RemovalArtifactStatus.ABSENT
    if not selected:
        return RemovalArtifactStatus.RETAINED
    return RemovalArtifactStatus.WOULD_REMOVE if dry_run else RemovalArtifactStatus.REMOVED


def _result(
    targets: tuple[_RemovalTarget, ...],
    *,
    include_decoders: bool,
    retain_schemas: bool,
    dry_run: bool,
) -> SdkRemovalResult:
    return SdkRemovalResult(
        dry_run=dry_run,
        include_decoders=include_decoders,
        retain_schemas=retain_schemas,
        records=tuple(
            SdkRemovalRecord(
                commit=target.commit,
                sdk_source=_artifact_status(target.sdk_source, selected=True, dry_run=dry_run),
                generated_schemas=_artifact_status(
                    target.generated_schemas,
                    selected=not retain_schemas,
                    dry_run=dry_run,
                ),
                decoder_runtime=_artifact_status(
                    target.decoder_runtime,
                    selected=include_decoders,
                    dry_run=dry_run,
                ),
                decoder_workspace=_artifact_status(
                    target.decoder_workspace,
                    selected=include_decoders,
                    dry_run=dry_run,
                ),
                active_sdk=target.active_sdk,
                active_schemas=target.active_schemas,
                active_decoder=target.active_decoder,
            )
            for target in targets
        ),
    )


def _remove_empty_root(root: Path) -> None:
    if root.is_dir() and not root.is_symlink():
        try:
            root.rmdir()
        except OSError:
            pass


def remove_sdk_artifacts(
    commits: Iterable[str] = (),
    *,
    remove_all: bool = False,
    include_decoders: bool = False,
    retain_schemas: bool = False,
    dry_run: bool = False,
    cache: SdkCache | None = None,
) -> SdkRemovalResult:
    """Remove exact SDK revisions and optionally their decoder artifacts."""
    cache = cache or SdkCache.default()
    targets = _targets(
        commits,
        remove_all=remove_all,
        include_decoders=include_decoders,
        retain_schemas=retain_schemas,
        cache=cache,
    )
    result = _result(
        targets,
        include_decoders=include_decoders,
        retain_schemas=retain_schemas,
        dry_run=dry_run,
    )
    if dry_run:
        return result
    for target in targets:
        if include_decoders:
            from polar_ble_tools.sdk_tools.decoder import remove_decoder

            remove_decoder(target.commit, cache=cache)
        remove_sdk(target.commit, retain_schemas=retain_schemas, cache=cache)
        if target.active_sdk:
            cache.active_manifest_path.unlink(missing_ok=True)
        if include_decoders and target.active_decoder:
            cache.active_decoder_manifest_path.unlink(missing_ok=True)
    if remove_all:
        cache.active_manifest_path.unlink(missing_ok=True)
        _remove_empty_root(cache.sdk_root)
        if not retain_schemas:
            cache.active_schema_manifest_path.unlink(missing_ok=True)
            _remove_empty_root(cache.generated_root)
        if include_decoders:
            cache.active_decoder_manifest_path.unlink(missing_ok=True)
            _remove_empty_root(cache.decoder_root)
            _remove_empty_root(cache.decoder_build_root)
    return result
