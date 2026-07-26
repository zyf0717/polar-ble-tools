from __future__ import annotations

import json
from pathlib import Path

import pytest

from polar_ble_tools.rec import DecoderVerificationError
from polar_ble_tools.schemas.cache import SdkCache
from polar_ble_tools.sdk_tools.decoder import (
    _promote_decoder_directory,
    _restore_decoder_directory,
    activate_decoder,
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
    cache.active_decoder_manifest_path.parent.mkdir(parents=True)
    cache.active_decoder_manifest_path.write_text(json.dumps({"sdk_commit": previous}), encoding="utf-8")
    manifest = cache.decoder_path(invalid) / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("{}", encoding="utf-8")

    with pytest.raises(DecoderVerificationError):
        activate_decoder(invalid, cache=cache)

    assert json.loads(cache.active_decoder_manifest_path.read_text(encoding="utf-8")) == {
        "sdk_commit": previous
    }
