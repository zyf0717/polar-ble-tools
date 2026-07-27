from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

from polar_ble_tools.rec import (
    DecoderProtocolError,
    DecoderTimeoutError,
    DecoderVerificationError,
    RecordingDecodeError,
    decode_recording,
    decoder_status,
    iter_decoded_records,
)
from polar_ble_tools.schemas.cache import SdkCache
from polar_ble_tools.sdk_tools.decoder.toolchain import (
    toolchain_descriptor,
    toolchain_descriptor_digest,
)

COMMIT = "a" * 40


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _decoder(cache: SdkCache, *, summary_count: int = 1, mode: str = "normal") -> Path:
    descriptor = toolchain_descriptor("linux", "x86_64")
    root = cache.decoder_path(COMMIT)
    executable = root / "bin" / "polar-rec-decoder"
    executable.parent.mkdir(parents=True)
    executable.write_text(
        "#!" + sys.executable + "\n"
        "import hashlib, json, pathlib, sys\n"
        "if sys.argv[1] in ('version', 'self-test'):\n"
        " print(json.dumps({'status':'ok','protocol_version':1,'sdk_commit':'"
        + COMMIT
        + "','decoder_version':'test'})); raise SystemExit(0)\n"
        f"if {mode!r} == 'timeout':\n"
        " import time; time.sleep(60)\n"
        f"if {mode!r} == 'oversized-status':\n"
        " print('x' * 9000); raise SystemExit(0)\n"
        "source = pathlib.Path(sys.argv[3]).read_bytes()\n"
        "output = pathlib.Path(sys.argv[5])\n"
        "digest = hashlib.sha256(source).hexdigest()\n"
        "rows = [{'type':'header','protocol_version':1,'sdk_commit':'"
        + COMMIT
        + "','decoder_version':'test','source_sha256':digest}, {'type':'record','record_type':'ppi','timestamp_ns':None,'payload':{'value':1}}, {'type':'summary','record_count':"
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
                "decoder_version": "test",
                "polar_ble_tools_version": "test",
                "platform": descriptor.platform,
                "architecture": descriptor.architecture,
                "java_version": descriptor.jdk_version,
                "java_archive_sha256": descriptor.jdk_sha256,
                "gradle_version": descriptor.gradle_version,
                "gradle_archive_sha256": descriptor.gradle_sha256,
                "adapter_source_sha256": "0" * 64,
                "toolchain_descriptor_sha256": toolchain_descriptor_digest(descriptor),
                "executable_relative_path": "bin/polar-rec-decoder",
                "executable_sha256": _digest(executable),
                "runtime_files": {
                    "bin/polar-rec-decoder": _digest(executable),
                },
                "runtime": {
                    "kind": "pinned-jvm",
                    "platform": "linux",
                    "architecture": "x86_64",
                    "java_version": descriptor.jdk_version,
                    "java_relative_cache_path": (
                        f"toolchains/rec-jvm/linux/x86_64/jdk-{descriptor.jdk_version}"
                    ),
                    "java_relative_path": descriptor.java_relative_path,
                    "java_executable_sha256": "",
                    "toolchain_descriptor_sha256": toolchain_descriptor_digest(descriptor),
                },
                "verification_level": "handshake",
                "verified": True,
            }
        ),
        encoding="utf-8",
    )
    cache.active_decoder_manifest_path.write_text(
        json.dumps({"sdk_commit": COMMIT}), encoding="utf-8"
    )
    java = (
        cache.rec_jvm_java_home("linux", "x86_64", descriptor.jdk_version)
        / descriptor.java_relative_path
    )
    java.parent.mkdir(parents=True)
    java.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    java.chmod(0o755)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    manifest["runtime"]["java_executable_sha256"] = _digest(java)
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return executable


def _use_cache(monkeypatch: pytest.MonkeyPatch, cache: SdkCache) -> None:
    monkeypatch.setattr(SdkCache, "default", classmethod(lambda cls: cache))


def test_decode_rejects_identical_source_and_output_without_starting_decoder(
    tmp_path: Path,
) -> None:
    source = tmp_path / "PPI0.REC"
    original = b"recording bytes"
    source.write_bytes(original)

    with pytest.raises(RecordingDecodeError, match="Output must differ"):
        decode_recording(source, source, overwrite=True)

    assert source.read_bytes() == original


def test_decode_rejects_relative_and_absolute_source_output_aliases(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "PPI0.REC"
    original = b"recording bytes"
    source.write_bytes(original)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(RecordingDecodeError, match="Output must differ"):
        decode_recording(source.name, source.resolve(), overwrite=True)

    assert source.read_bytes() == original


def test_decode_rejects_hardlinked_source_and_output(tmp_path: Path) -> None:
    source, output = tmp_path / "PPI0.REC", tmp_path / "decoded.jsonl"
    original = b"recording bytes"
    source.write_bytes(original)
    os.link(source, output)

    with pytest.raises(RecordingDecodeError, match="Output must differ"):
        decode_recording(source, output, overwrite=True)

    assert source.read_bytes() == original
    assert output.read_bytes() == original


def test_decode_overwrite_rejects_unrelated_existing_file(tmp_path: Path) -> None:
    source, output = tmp_path / "PPI0.REC", tmp_path / "decoded.jsonl"
    source.write_bytes(b"recording bytes")
    output.write_text("unrelated\n", encoding="utf-8")

    with pytest.raises(RecordingDecodeError, match="project-owned"):
        decode_recording(source, output, overwrite=True)

    assert output.read_text(encoding="utf-8") == "unrelated\n"


def test_decode_recording_validates_and_iterates(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cache = SdkCache(tmp_path / "cache")
    _decoder(cache)
    _use_cache(monkeypatch, cache)
    source, output = tmp_path / "PPI0.REC", tmp_path / "decoded.jsonl"
    source.write_bytes(b"sample")

    report = decode_recording(source, output)

    assert report.record_count == 1
    assert list(iter_decoded_records(output))[0].payload == {"value": 1}
    assert decoder_status().available


def test_decode_rejects_inconsistent_summary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cache = SdkCache(tmp_path / "cache")
    _decoder(cache, summary_count=2)
    _use_cache(monkeypatch, cache)
    source = tmp_path / "PPI0.REC"
    source.write_bytes(b"sample")

    with pytest.raises(DecoderProtocolError, match="summary"):
        decode_recording(source, tmp_path / "decoded.jsonl")


def test_decoder_rejects_unmanifested_runtime_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cache = SdkCache(tmp_path / "cache")
    _decoder(cache)
    _use_cache(monkeypatch, cache)
    (cache.decoder_path(COMMIT) / "lib").mkdir()
    (cache.decoder_path(COMMIT) / "lib" / "unexpected.jar").write_bytes(b"not trusted")
    source = tmp_path / "PPI0.REC"
    source.write_bytes(b"sample")

    with pytest.raises(DecoderVerificationError, match="runtime files changed"):
        decode_recording(source, tmp_path / "decoded.jsonl")


def test_status_rejects_legacy_package_managed_decoder_cache(tmp_path: Path) -> None:
    cache = SdkCache(tmp_path / "cache")
    _decoder(cache)
    root = cache.decoder_path(COMMIT)
    legacy_files = (
        root / "licenses" / "Polar_SDK_License.txt",
        root / "notices" / "ThirdPartySoftwareListing.txt",
    )
    for path in legacy_files:
        path.parent.mkdir()
        path.write_text("legacy cache material\n", encoding="utf-8")
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["runtime_files"].update(
        {path.relative_to(root).as_posix(): _digest(path) for path in legacy_files}
    )
    manifest["license_material"] = [{"legacy": True}]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    status = decoder_status(cache=cache)

    assert not status.available
    assert "Legacy package-managed decoder cache is unsupported" in (status.reason or "")
    assert "polar-ble sdk decoder build" in (status.reason or "")


def test_status_reports_actionable_architecture_mismatch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cache = SdkCache(tmp_path / "cache")
    _decoder(cache)
    monkeypatch.setattr("polar_ble_tools.rec.api.platform.machine", lambda: "aarch64")

    status = decoder_status(cache=cache)

    assert not status.available
    assert "polar-ble sdk decoder build" in (status.reason or "")


def test_decode_timeout_terminates_child_and_removes_temporary_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cache = SdkCache(tmp_path / "cache")
    _decoder(cache, mode="timeout")
    _use_cache(monkeypatch, cache)
    source, output = tmp_path / "PPI0.REC", tmp_path / "decoded.jsonl"
    source.write_bytes(b"sample")

    with pytest.raises(DecoderTimeoutError):
        decode_recording(source, output, timeout_seconds=0.05)

    assert not output.exists()
    assert not list(tmp_path.glob(".decoded.jsonl.*.jsonl"))


def test_decode_rejects_oversized_status(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cache = SdkCache(tmp_path / "cache")
    _decoder(cache, mode="oversized-status")
    _use_cache(monkeypatch, cache)
    source = tmp_path / "PPI0.REC"
    source.write_bytes(b"sample")

    with pytest.raises(DecoderProtocolError, match="maximum size"):
        decode_recording(source, tmp_path / "decoded.jsonl")


@pytest.mark.parametrize(
    "record",
    [
        '{"type":"record","record_type":"PPI","timestamp_ns":null,"payload":{}}',
        '{"type":"record","record_type":"ppi","timestamp_ns":true,"payload":{}}',
        '{"type":"record","record_type":"ppi","timestamp_ns":NaN,"payload":{}}',
    ],
)
def test_iter_rejects_invalid_streaming_record(tmp_path: Path, record: str) -> None:
    source_digest = "0" * 64
    decoded = tmp_path / "decoded.jsonl"
    decoded.write_text(
        "\n".join(
            (
                json.dumps(
                    {
                        "type": "header",
                        "protocol_version": 1,
                        "sdk_commit": COMMIT,
                        "decoder_version": "test",
                        "source_sha256": source_digest,
                    }
                ),
                record,
                '{"type":"summary","record_count":1,"record_types":{"ppi":1},"warnings":[]}',
            )
        ),
        encoding="utf-8",
    )

    with pytest.raises(DecoderProtocolError):
        list(iter_decoded_records(decoded))


def test_iter_rejects_row_after_summary(tmp_path: Path) -> None:
    source_digest = "0" * 64
    decoded = tmp_path / "decoded.jsonl"
    decoded.write_text(
        "\n".join(
            (
                json.dumps(
                    {
                        "type": "header",
                        "protocol_version": 1,
                        "sdk_commit": COMMIT,
                        "decoder_version": "test",
                        "source_sha256": source_digest,
                    }
                ),
                '{"type":"summary","record_count":0,"record_types":{},"warnings":[]}',
                '{"type":"record","record_type":"ppi","timestamp_ns":null,"payload":{}}',
            )
        ),
        encoding="utf-8",
    )

    with pytest.raises(DecoderProtocolError, match="after its summary"):
        list(iter_decoded_records(decoded))
