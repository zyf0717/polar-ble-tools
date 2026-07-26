from __future__ import annotations

import asyncio
from types import SimpleNamespace

from polar_ble_tools.api import apply_ftu, doctor
from polar_ble_tools.rec import DecoderStatus
from polar_ble_tools.schemas.cache import SdkCache
from polar_ble_tools.sdk_tools.downloader import SdkStatus


def test_doctor_returns_structured_unavailable_optional_features(monkeypatch, tmp_path) -> None:
    cache = SdkCache(tmp_path / "cache")
    monkeypatch.setattr(
        "polar_ble_tools.sdk_tools.downloader.sdk_status", lambda *, cache: SdkStatus(None, ())
    )
    monkeypatch.setattr(
        "polar_ble_tools.rec.decoder_status",
        lambda *, cache: DecoderStatus(False, False, None, None, None, "not built"),
    )

    report = doctor(cache=cache)

    assert not report.schemas.ready
    assert report.schemas.remediation == "polar-ble sdk install --accept-license"
    assert report.to_dict()["decoder"]["reason"] == "not built"


def test_apply_ftu_owns_session_and_applies_initial_settings(monkeypatch) -> None:
    calls: list[object] = []

    class Setup:
        async def do_first_time_use(self, profile: object) -> None:
            calls.append(("apply", profile))

        async def set_user_device_settings(self, patch: object) -> None:
            calls.append(("settings", patch))

    class Device:
        services = SimpleNamespace(setup=Setup())

        async def __aenter__(self):
            calls.append("enter")
            return self

        async def __aexit__(self, *_):
            calls.append("exit")

    monkeypatch.setattr("polar_ble_tools.api._device", lambda *_: Device())
    patch = SimpleNamespace(has_changes=True)
    profile = SimpleNamespace(user_device_settings=patch)

    result = asyncio.run(apply_ftu("AA:BB:CC:DD:EE:FF", profile))

    assert result.ftu_applied and result.settings_updated
    assert calls == ["enter", ("apply", profile), ("settings", patch), "exit"]
