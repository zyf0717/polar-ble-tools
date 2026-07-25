from __future__ import annotations

from polar_ble_tools.commands.main import main


def test_primary_cli_lists_available_commands(capsys) -> None:
    assert main([]) == 0

    output = capsys.readouterr().out
    assert "pair" in output
    assert "connect" in output
    assert "discover" in output
    assert "ftu" in output
    assert "raw" in output
    assert "passive" in output
    assert "bpb" in output
    assert "sdk" in output
    assert "doctor" in output
