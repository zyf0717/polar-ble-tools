from __future__ import annotations

import json

from polar_ble_tools.ble.transport import (
    DevicePlatform,
    PreparationOutcome,
    PreparationResult,
    ProbeResult,
    ReconnectPersistence,
)
from polar_ble_tools.commands.lifecycle import connect_main, prepare_main
from polar_ble_tools.polar.uuids import PFTP_SERVICE, PMD_SERVICE


def test_prepare_cli_prints_deterministic_json(monkeypatch, capsys) -> None:
    async def fake_prepare(identifier: str, *, devices_file: str | None):
        assert identifier == "AA:BB:CC:DD:EE:FF"
        assert devices_file is None
        return PreparationResult(
            identifier=identifier,
            platform=DevicePlatform.LINUX,
            outcome=PreparationOutcome.READY,
            readiness_verified=True,
            reconnect_persistence=ReconnectPersistence.VERIFIED,
            final_connected=False,
        )

    monkeypatch.setattr("polar_ble_tools.commands.lifecycle.prepare_device", fake_prepare)

    assert prepare_main(["--device-identifier", "AA:BB:CC:DD:EE:FF"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "identifier": "AA:BB:CC:DD:EE:FF",
        "platform": "linux",
        "outcome": "ready",
        "readiness_verified": True,
        "reconnect_persistence": "verified",
        "final_connected": False,
    }


def test_connect_cli_is_bounded_probe_ending_disconnected(monkeypatch, capsys) -> None:
    async def fake_probe(identifier: str, *, devices_file: str | None):
        assert identifier == "AA:BB:CC:DD:EE:FF"
        assert devices_file is None
        return ProbeResult(
            identifier=identifier,
            platform=DevicePlatform.LINUX,
            readiness_verified=True,
            service_uuids=(PFTP_SERVICE, PMD_SERVICE),
            final_connected=False,
        )

    monkeypatch.setattr("polar_ble_tools.commands.lifecycle.probe_device", fake_probe)

    assert connect_main(["--device-identifier", "AA:BB:CC:DD:EE:FF"]) == 0
    assert json.loads(capsys.readouterr().out)["final_connected"] is False
