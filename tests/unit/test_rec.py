from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

from polar_ble_tools.rec import (
    DecoderProtocolError,
    decode_recording,
    decoder_status,
    iter_decoded_records,
)
from polar_ble_tools.schemas.cache import SdkCache

COMMIT = "a" * 40


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _decoder(cache: SdkCache, *, summary_count: int = 1) -> Path:
    root = cache.decoder_path(COMMIT)
    executable = root / "bin" / "polar-rec-decoder"
    executable.parent.mkdir(parents=True)
    executable.write_text(
        "#!" + sys.executable + "\n"
        "import hashlib, json, pathlib, sys\n"
        "if sys.argv[1] in ('version', 'self-test'):\n"
        " print(json.dumps({'status':'ok','protocol_version':1})); raise SystemExit(0)\n"
        "source = pathlib.Path(sys.argv[3]).read_bytes()\n"
        "output = pathlib.Path(sys.argv[5])\n"
        "digest = hashlib.sha256(source).hexdigest()\n"
        "rows = [{'type':'header','protocol_version':1,'sdk_commit':'" + COMMIT + "','decoder_version':'test','source_sha256':digest}, {'type':'record','record_type':'ppi','timestamp_ns':None,'payload':{'value':1}}, {'type':'summary','record_count':"
        + str(summary_count)
        + ",'record_types':{'ppi':1},'warnings':[]}]\n"
        "output.write_text('\\n'.join(json.dumps(row) for row in rows) + '\\n')\n"
        "print(json.dumps({'status':'ok','record_count':1}))\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "manifest_version": 1,
                "decoder_protocol_version": 1,
                "sdk_commit": COMMIT,
                "executable_relative_path": "bin/polar-rec-decoder",
                "executable_sha256": _digest(executable),
                "verification_level": "handshake",
                "verified": True,
            }
        ),
        encoding="utf-8",
    )
    cache.active_decoder_manifest_path.write_text(json.dumps({"sdk_commit": COMMIT}), encoding="utf-8")
    java = cache.decoder_build_path(COMMIT) / "tools" / "jdk-21.0.12+8" / "bin" / "java"
    java.parent.mkdir(parents=True)
    java.symlink_to(Path(sys.executable))
    return executable


def _use_cache(monkeypatch: pytest.MonkeyPatch, cache: SdkCache) -> None:
    monkeypatch.setattr(SdkCache, "default", classmethod(lambda cls: cache))


def test_decode_recording_validates_and_iterates(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cache = SdkCache(tmp_path / "cache")
    _decoder(cache)
    _use_cache(monkeypatch, cache)
    source, output = tmp_path / "PPI0.REC", tmp_path / "decoded.jsonl"
    source.write_bytes(b"sample")

    report = decode_recording(source, output)

    assert report.record_count == 1
    assert list(iter_decoded_records(output))[0].payload == {"value": 1}
    assert decoder_status().available


def test_decode_rejects_inconsistent_summary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cache = SdkCache(tmp_path / "cache")
    _decoder(cache, summary_count=2)
    _use_cache(monkeypatch, cache)
    source = tmp_path / "PPI0.REC"
    source.write_bytes(b"sample")

    with pytest.raises(DecoderProtocolError, match="summary"):
        decode_recording(source, tmp_path / "decoded.jsonl")
