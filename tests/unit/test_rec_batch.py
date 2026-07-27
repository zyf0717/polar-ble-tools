from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from polar_ble_tools.commands.rec import rec_main
from polar_ble_tools.rec import (
    DecodeReport,
    DecoderManifestError,
    RecordingDecodeError,
    UnsupportedRecordingError,
    decode_recording_manifest,
    decode_recording_tree,
)

COMMIT = "a" * 40


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fake_decoder(calls: list[str]):
    def decode(
        source: Path,
        destination: Path,
        *,
        overwrite: bool,
        timeout_seconds: float | None,
    ) -> DecodeReport:
        calls.append(source.name)
        if source.name.startswith("unsupported"):
            raise UnsupportedRecordingError("unsupported recording")
        if source.name.startswith("failed"):
            raise RecordingDecodeError(f"failed to decode {source}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text('{"decoded":true}\n', encoding="utf-8")
        return DecodeReport(
            source,
            destination,
            _digest(source),
            _digest(destination),
            COMMIT,
            "test",
            2,
            {"acc": 2},
            (),
        )

    return decode


def _write_decoded(path: Path, source_digest: str = "0" * 64) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = (
        {
            "type": "header",
            "protocol_version": 1,
            "sdk_commit": COMMIT,
            "decoder_version": "test",
            "source_sha256": source_digest,
        },
        {
            "type": "summary",
            "record_count": 0,
            "record_types": {},
            "warnings": [],
        },
    )
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_tree_decode_is_deterministic_and_excludes_symlinks_and_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "source"
    output = source / "decoded"
    (source / "nested").mkdir(parents=True)
    output.mkdir()
    for relative in ("B.REC", "a.rec", "nested/c.REC", "decoded/ignored.REC"):
        path = source / relative
        path.write_bytes(relative.encode())
    outside = tmp_path / "outside.REC"
    outside.write_bytes(b"outside")
    (source / "linked.REC").symlink_to(outside)
    calls: list[str] = []
    monkeypatch.setattr("polar_ble_tools.rec.batch.decode_recording", _fake_decoder(calls))

    report = decode_recording_tree(source, output)

    assert [item.relative_path for item in report.files] == [
        "B.REC",
        "a.rec",
        "nested/c.REC",
    ]
    assert calls == ["B.REC", "a.rec", "c.REC"]
    assert report.decoded == 3
    assert report.failed == 0
    assert report.record_count == 6
    assert report.record_types == {"acc": 6}
    assert (output / "B.jsonl").is_file()
    assert (output / "nested" / "c.jsonl").is_file()
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert [item["relative_path"] for item in summary["files"]] == [
        "B.REC",
        "a.rec",
        "nested/c.REC",
    ]


def test_batch_continues_after_unsupported_and_failed_sources(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source, output = tmp_path / "source", tmp_path / "output"
    source.mkdir()
    for name in ("decoded.REC", "failed.REC", "unsupported.REC"):
        (source / name).write_bytes(name.encode())
    monkeypatch.setattr("polar_ble_tools.rec.batch.decode_recording", _fake_decoder([]))

    report = decode_recording_tree(source, output)

    assert report.decoded == 1
    assert report.unsupported == 1
    assert report.failed == 1
    assert not report.ok
    assert [item.status for item in report.files] == [
        "decoded",
        "failed",
        "unsupported",
    ]
    assert report.files[1].error_code == "decode_failed"
    assert str(source) not in (report.files[1].error or "")
    assert report.files[2].error_code == "unsupported_recording"


def test_tree_preflights_all_destinations_before_decoding(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source, output = tmp_path / "source", tmp_path / "output"
    source.mkdir()
    (source / "first.REC").write_bytes(b"first")
    (source / "second.REC").write_bytes(b"second")
    output.mkdir()
    (output / "second.jsonl").write_text("unrelated\n", encoding="utf-8")
    calls: list[str] = []
    monkeypatch.setattr("polar_ble_tools.rec.batch.decode_recording", _fake_decoder(calls))

    with pytest.raises(DecoderManifestError, match="already exists"):
        decode_recording_tree(source, output)

    assert calls == []
    assert not (output / "first.jsonl").exists()


def test_overwrite_accepts_only_project_owned_outputs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source, output = tmp_path / "source", tmp_path / "output"
    source.mkdir()
    recording = source / "ACC.REC"
    recording.write_bytes(b"recording")
    output.mkdir()
    destination = output / "ACC.jsonl"
    destination.write_text("unrelated\n", encoding="utf-8")
    monkeypatch.setattr("polar_ble_tools.rec.batch.decode_recording", _fake_decoder([]))

    with pytest.raises(DecoderManifestError, match="project-owned"):
        decode_recording_tree(source, output, overwrite=True)

    _write_decoded(destination)
    (output / "summary.json").write_text(
        json.dumps(
            {
                "kind": "polar_ble_tools_rec_batch_summary",
                "schema_version": 1,
            }
        ),
        encoding="utf-8",
    )
    report = decode_recording_tree(source, output, overwrite=True)
    assert report.decoded == 1


def _write_manifest(path: Path, *rows: dict[str, object], newline: bool = True) -> None:
    payload = "\n".join(json.dumps(row) for row in rows)
    path.write_text(payload + ("\n" if newline else ""), encoding="utf-8")


def test_manifest_decode_validates_digest_and_orders_sources(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source, output = tmp_path / "source", tmp_path / "output"
    source.mkdir()
    first, second = source / "z.REC", source / "a.REC"
    first.write_bytes(b"z")
    second.write_bytes(b"a")
    manifest = tmp_path / "manifest.jsonl"
    _write_manifest(
        manifest,
        {"schema_version": 1, "source": "z.REC"},
        {
            "schema_version": 1,
            "source": "a.REC",
            "source_sha256": _digest(second),
        },
    )
    calls: list[str] = []
    monkeypatch.setattr("polar_ble_tools.rec.batch.decode_recording", _fake_decoder(calls))

    report = decode_recording_manifest(manifest, source, output)

    assert [item.relative_path for item in report.files] == ["a.REC", "z.REC"]
    assert calls == ["a.REC", "z.REC"]


@pytest.mark.parametrize(
    ("payload", "match"),
    [
        ('{"schema_version":1,"source":"../escape.REC"}\n', "source path"),
        ('{"schema_version":1,"source":"a//b.REC"}\n', "source path"),
        ('{"schema_version":true,"source":"a.REC"}\n', "schema version"),
        (
            '{"schema_version":1,"source":"a.REC","inline_secret":"value"}\n',
            "unknown fields",
        ),
        (
            '{"schema_version":1,"schema_version":1,"source":"a.REC"}\n',
            "invalid JSON",
        ),
        ('{"schema_version":1,"source":"a.REC"}', "end with a newline"),
    ],
)
def test_manifest_rejects_malformed_rows(tmp_path: Path, payload: str, match: str) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "a.REC").write_bytes(b"a")
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(payload, encoding="utf-8")

    with pytest.raises(DecoderManifestError, match=match):
        decode_recording_manifest(manifest, source, tmp_path / "output")


def test_manifest_rejects_symlink_and_digest_mismatch(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    target = source / "target.REC"
    target.write_bytes(b"target")
    (source / "linked.REC").symlink_to(target)
    manifest = tmp_path / "manifest.jsonl"
    _write_manifest(manifest, {"schema_version": 1, "source": "linked.REC"})

    with pytest.raises(DecoderManifestError, match="missing or unsafe"):
        decode_recording_manifest(manifest, source, tmp_path / "output")

    _write_manifest(
        manifest,
        {
            "schema_version": 1,
            "source": "target.REC",
            "source_sha256": "0" * 64,
        },
    )
    with pytest.raises(DecoderManifestError, match="digest does not match"):
        decode_recording_manifest(manifest, source, tmp_path / "output")


def test_manifest_secret_id_fails_before_decoder_without_provider(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "a.REC").write_bytes(b"a")
    manifest = tmp_path / "manifest.jsonl"
    _write_manifest(
        manifest,
        {"schema_version": 1, "source": "a.REC", "secret_id": "key-a"},
    )
    calls: list[str] = []
    monkeypatch.setattr("polar_ble_tools.rec.batch.decode_recording", _fake_decoder(calls))

    with pytest.raises(DecoderManifestError, match="protected protocol"):
        decode_recording_manifest(manifest, source, tmp_path / "output")

    assert calls == []


def test_batch_cli_exit_status_tracks_failed_files(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    report = SimpleNamespace(
        ok=False,
        to_jsonable=lambda: {"schema_version": 1, "failed": 1},
    )
    monkeypatch.setattr(
        "polar_ble_tools.commands.rec.decode_recording_tree",
        lambda *_args, **_kwargs: report,
    )

    assert rec_main(["decode-tree", "input", "--output-root", "output"]) == 1
    assert json.loads(capsys.readouterr().out)["failed"] == 1
