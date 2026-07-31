from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from polar_ble_tools.commands.passive import passive_main
from polar_ble_tools.polar.passive import PassiveDomain, PassiveFileEntry, PassiveFileListing


def _inventory(tmp_path: Path) -> Path:
    path = tmp_path / "devices.yaml"
    path.write_text("polar:\n  - AA:BB:CC:DD:EE:FF\n", encoding="utf-8")
    return path


def test_passive_cli_lists_raw_files_without_schema_cache(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    async def fake_list(*args, **kwargs) -> PassiveFileListing:
        assert kwargs["domains"] == (PassiveDomain.DAILY_SUMMARY,)
        return PassiveFileListing(
            [
                PassiveFileEntry(
                    PassiveDomain.DAILY_SUMMARY,
                    "/U/0/20260625/DSUM/DSUM.BPB",
                    3,
                    date(2026, 6, 25),
                )
            ],
            [],
        )

    monkeypatch.setattr("polar_ble_tools.commands.passive.list_passive_files", fake_list)
    assert (
        passive_main(
            [
                "--device-identifier",
                "AA:BB:CC:DD:EE:FF",
                "--devices-file",
                str(_inventory(tmp_path)),
                "--from-date",
                "2026-06-25",
                "--domain",
                "daily_summary",
                "list",
            ]
        )
        == 0
    )
    output = json.loads(capsys.readouterr().out)
    assert output["records"][0]["path"] == "/U/0/20260625/DSUM/DSUM.BPB"


def test_passive_cli_rejects_unauthorized_device(tmp_path: Path, capsys) -> None:
    assert (
        passive_main(
            [
                "--device-identifier",
                "11:22:33:44:55:66",
                "--devices-file",
                str(_inventory(tmp_path)),
                "--from-date",
                "2026-06-25",
                "list",
            ]
        )
        == 2
    )
    assert "not authorized" in capsys.readouterr().err


def test_passive_collect_passes_existing_file_policy(monkeypatch, capsys) -> None:
    class Result:
        ok = True

        def to_jsonable(self):
            return {"fetched": 1}

    async def fake_collect(*_args, **kwargs):
        assert kwargs["existing_file_policy"] == "overwrite"
        return Result()

    monkeypatch.setattr("polar_ble_tools.commands.passive.collect_passive_files", fake_collect)

    assert (
        passive_main(
            [
                "--device-identifier",
                "AA:BB:CC:DD:EE:FF",
                "--from-date",
                "2026-06-25",
                "collect",
                "--existing-file-policy",
                "overwrite",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out) == {"fetched": 1}


def test_passive_collect_decode_reports_collection_and_decode_outcomes(monkeypatch, capsys) -> None:
    class CollectionResult:
        ok = True
        manifest_path = "/store/DEVICE/manifest.jsonl"

        def to_jsonable(self):
            return {"fetched": 1}

    class DecodeResult:
        ok = False

        def to_jsonable(self):
            return {"decoded": 0, "failed": 1}

    async def fake_collect(*_args, **_kwargs):
        return CollectionResult()

    monkeypatch.setattr("polar_ble_tools.commands.passive.collect_passive_files", fake_collect)
    monkeypatch.setattr(
        "polar_ble_tools.commands.passive.decode_passive_manifest",
        lambda *_args, **_kwargs: DecodeResult(),
    )

    assert (
        passive_main(
            [
                "--device-identifier",
                "AA:BB:CC:DD:EE:FF",
                "--from-date",
                "2026-06-25",
                "collect",
                "--decode",
            ]
        )
        == 1
    )
    assert json.loads(capsys.readouterr().out) == {
        "collection": {"fetched": 1},
        "decoding": {"decoded": 0, "failed": 1},
    }


def test_passive_cleanup_dry_run_does_not_require_collection_dates(monkeypatch, capsys) -> None:
    class Result:
        ok = True

        def to_jsonable(self):
            return {"dry_run": 1}

    async def fake_cleanup(*args, **kwargs):
        assert args == ("AA:BB:CC:DD:EE:FF",)
        assert kwargs["domain"] == "daily_summary"
        assert kwargs["dry_run"] is True
        assert kwargs["delete_through"] == date(2026, 6, 25)
        return Result()

    monkeypatch.setattr("polar_ble_tools.commands.passive.cleanup_passive_files", fake_cleanup)

    assert (
        passive_main(
            [
                "--device-identifier",
                "AA:BB:CC:DD:EE:FF",
                "cleanup",
                "--domain",
                "daily_summary",
                "--delete-through",
                "2026-06-25",
                "--dry-run",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out) == {"dry_run": 1}
