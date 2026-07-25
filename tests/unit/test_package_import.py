from __future__ import annotations

import importlib
import os
import subprocess
import sys
import tomllib
from pathlib import Path


def test_package_imports_without_generated_schemas() -> None:
    package = importlib.import_module("polar_ble_tools")

    assert package.__version__ == "0.1.1"
    assert callable(package.discover_devices)
    assert callable(package.pair_device)
    assert callable(package.connect_device)
    assert not any(
        module_name.startswith("polar_ble_tools._generated") for module_name in sys.modules
    )


def test_package_version_matches_project_metadata() -> None:
    project_root = Path(__file__).resolve().parents[2]
    with (project_root / "pyproject.toml").open("rb") as metadata:
        project = tomllib.load(metadata)["project"]
    assert importlib.import_module("polar_ble_tools").__version__ == project["version"]


def test_schema_free_import_and_help_do_not_touch_cache_or_network(tmp_path: Path) -> None:
    data_home = tmp_path / "user-data"
    environment = {
        **os.environ,
        "XDG_DATA_HOME": str(data_home),
    }
    script = """
import socket
import sys

def blocked(*args, **kwargs):
    raise AssertionError("network access is forbidden in schema-free commands")

socket.create_connection = blocked
socket.socket.connect = blocked
from polar_ble_tools.commands.main import main
try:
    main(sys.argv[1:])
except SystemExit as exc:
    if exc.code not in (0, None):
        raise
assert not any(name.endswith('_pb2') for name in sys.modules)
"""
    for arguments in (
        (),
        ("--help",),
        ("discover", "--help"),
        ("pair", "--help"),
        ("raw", "--help"),
    ):
        completed = subprocess.run(
            [sys.executable, "-c", script, *arguments],
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr
    assert not (data_home / "polar-ble-tools").exists()
