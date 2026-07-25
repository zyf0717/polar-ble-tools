from __future__ import annotations

import json

from polar_ble_tools.ble.transport import BluetoothDevice
from polar_ble_tools.commands.discover import discover_main


def test_discover_cli_prints_read_only_candidates(monkeypatch, capsys) -> None:
    def fake_discover(**kwargs):
        assert kwargs == {
            "scan_seconds": 2.0,
            "name_substring": "Polar",
            "executable": "bluetoothctl",
        }
        return [
            BluetoothDevice(
                mac_address="AA:BB:CC:DD:EE:FF",
                name="Polar Loop Gen 2",
                rssi=-47,
            )
        ]

    monkeypatch.setattr("polar_ble_tools.commands.discover.discover_devices", fake_discover)

    assert discover_main(["--scan-seconds", "2", "--name", "Polar"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "discovered": 1,
        "devices": [
            {
                "mac_address": "AA:BB:CC:DD:EE:FF",
                "name": "Polar Loop Gen 2",
                "rssi": -47,
            }
        ],
    }
