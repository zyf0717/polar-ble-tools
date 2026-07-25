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
                "--mac-address",
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
                "--mac-address",
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
