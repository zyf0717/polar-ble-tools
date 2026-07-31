from __future__ import annotations

import json

from polar_ble_tools.ble.transport import DevicePlatform, DiscoveredDevice
from polar_ble_tools.commands.discover import discover_main


def test_discover_cli_prints_structured_read_only_candidates(monkeypatch, capsys) -> None:
    async def fake_scan_devices(**kwargs):
        assert kwargs == {
            "timeout": 2.0,
            "name_substring": "Polar",
        }
        return (
            DiscoveredDevice(
                identifier="AA:BB:CC:DD:EE:FF",
                platform=DevicePlatform.LINUX,
                name="Polar Loop Gen 2",
                rssi=-47,
                service_uuids=("feee",),
            ),
        )

    monkeypatch.setattr(
        "polar_ble_tools.commands.discover.scan_devices",
        fake_scan_devices,
    )

    assert discover_main(["--timeout", "2", "--name", "Polar"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "count": 1,
        "devices": [
            {
                "identifier": "AA:BB:CC:DD:EE:FF",
                "platform": "linux",
                "name": "Polar Loop Gen 2",
                "rssi": -47,
                "service_uuids": ["feee"],
            }
        ],
    }
