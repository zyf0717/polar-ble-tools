from __future__ import annotations

from polar_ble_tools.commands.ftu import build_ftu_parser
from polar_ble_tools.commands.lifecycle import build_connect_parser, build_prepare_parser
from polar_ble_tools.commands.main import main
from polar_ble_tools.commands.passive import build_passive_parser
from polar_ble_tools.commands.raw import build_raw_parser


def test_primary_cli_lists_available_commands(capsys) -> None:
    assert main([]) == 0

    output = capsys.readouterr().out
    assert "prepare" in output
    assert "pair" not in output
    assert "connect" in output
    assert "discover" in output
    assert "ftu" in output
    assert "raw" in output
    assert "passive" in output
    assert "bpb" in output
    assert "rec" in output
    assert "sdk" in output
    assert "doctor" in output


def test_removed_mac_option_is_absent_from_every_device_parser() -> None:
    for parser in (
        build_prepare_parser(),
        build_connect_parser(),
        build_raw_parser(),
        build_passive_parser(),
        build_ftu_parser(),
    ):
        assert "--mac-address" not in parser.format_help()
