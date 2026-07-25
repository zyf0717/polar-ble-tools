from __future__ import annotations

import json

from polar_ble_tools.commands.doctor import doctor_main
from polar_ble_tools.sdk_tools.downloader import SdkStatus


def test_doctor_reports_core_ready_and_missing_schemas(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "polar_ble_tools.commands.doctor.sdk_status",
        lambda: SdkStatus(active_commit=None, installed_commits=()),
    )

    assert doctor_main([]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["core"] == {"ready": True}
    assert output["schemas"]["ready"] is False
    assert output["schemas"]["remediation"] == "polar-ble sdk install --accept-license"
