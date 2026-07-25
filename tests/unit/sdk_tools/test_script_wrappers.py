from __future__ import annotations

import runpy
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    ("script", "command"),
    [
        ("download_polar_sdk", "download"),
        ("inspect_polar_sdk", "inspect"),
        ("generate_polar_schemas", "generate"),
        ("verify_polar_schemas", "verify"),
    ],
)
def test_sdk_script_wrapper_forwards_to_package_cli(
    monkeypatch: pytest.MonkeyPatch,
    script: str,
    command: str,
) -> None:
    import polar_ble_tools.sdk_tools.cli as cli

    forwarded: list[list[str]] = []
    monkeypatch.setattr(cli, "main", lambda argv: forwarded.append(argv) or 7)
    monkeypatch.setattr(sys, "argv", [script, "--example"])
    path = Path(__file__).parents[3] / "scripts" / script

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_path(path, run_name="__main__")

    assert exc_info.value.code == 7
    assert forwarded == [[command, "--example"]]
