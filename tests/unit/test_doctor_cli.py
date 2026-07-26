from __future__ import annotations

import json

from polar_ble_tools.api import DoctorReport, DoctorSchemaStatus
from polar_ble_tools.commands.doctor import doctor_main
from polar_ble_tools.rec import DecoderStatus
from polar_ble_tools.sdk_tools.downloader import SdkStatus


def test_doctor_reports_core_ready_and_missing_schemas(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "polar_ble_tools.commands.doctor.doctor",
        lambda: DoctorReport(
            sdk=SdkStatus(active_commit=None, installed_commits=()),
            schemas=DoctorSchemaStatus(
                ready=False, remediation="polar-ble sdk install --accept-license"
            ),
            decoder=DecoderStatus(False, False, None, None, None, "decoder unavailable"),
        ),
    )

    assert doctor_main([]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["core"] == {"ready": True}
    assert output["schemas"]["ready"] is False
    assert output["schemas"]["remediation"] == "polar-ble sdk install --accept-license"
    assert output["decoder"] == {
        "available": False,
        "protocol_version": None,
        "reason": "decoder unavailable",
        "sdk_commit": None,
        "verification_level": None,
        "verified": False,
    }
