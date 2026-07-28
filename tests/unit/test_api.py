from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

import polar_ble_tools.api as public_api
from polar_ble_tools.api import apply_ftu, doctor
from polar_ble_tools.polar._protobuf import PftpDiskSpace
from polar_ble_tools.polar.offline import OfflineRecordingTrigger
from polar_ble_tools.polar.pmd import (
    PmdOfflineRecTriggerMode,
    PmdSetting,
    PmdSettingType,
    PolarDeviceDataType,
)
from polar_ble_tools.rec import DecoderStatus
from polar_ble_tools.schemas.cache import SdkCache
from polar_ble_tools.sdk_tools.downloader import SdkStatus
from polar_ble_tools.sdk_tools.verifier import SchemaStatus


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
    assert report.schemas.remediation == "polar-ble sdk install"
    assert report.to_dict()["decoder"]["reason"] == "not built"
    assert report.warnings == ()


def test_doctor_warns_without_invalidating_mismatched_decoder(monkeypatch, tmp_path) -> None:
    cache = SdkCache(tmp_path / "cache")
    sdk_commit, decoder_commit = "a" * 40, "b" * 40
    monkeypatch.setattr(
        "polar_ble_tools.sdk_tools.downloader.sdk_status",
        lambda *, cache: SdkStatus(sdk_commit, (sdk_commit,)),
    )
    monkeypatch.setattr(
        "polar_ble_tools.sdk_tools.verifier.verify_active_schemas",
        lambda *, cache: tmp_path / "schemas",
    )
    monkeypatch.setattr(
        "polar_ble_tools.sdk_tools.verifier.schema_status",
        lambda *, cache: SchemaStatus(sdk_commit, (sdk_commit,), 3, True),
    )
    monkeypatch.setattr(
        "polar_ble_tools.rec.decoder_status",
        lambda *, cache: DecoderStatus(True, True, decoder_commit, 1, "handshake", None),
    )

    report = doctor(cache=cache)

    assert report.decoder.available
    assert len(report.warnings) == 1
    assert sdk_commit in report.warnings[0]
    assert decoder_commit in report.warnings[0]
    assert "polar-ble sdk decoder build" in report.warnings[0]
    assert report.to_dict()["warnings"] == list(report.warnings)


def test_doctor_reports_retained_active_schemas_without_sdk_source(monkeypatch, tmp_path) -> None:
    cache = SdkCache(tmp_path / "cache")
    commit = "a" * 40
    monkeypatch.setattr(
        "polar_ble_tools.sdk_tools.downloader.sdk_status",
        lambda *, cache: SdkStatus(None, ()),
    )
    monkeypatch.setattr(
        "polar_ble_tools.sdk_tools.verifier.schema_status",
        lambda *, cache: SchemaStatus(commit, (commit,), 3, True),
    )
    monkeypatch.setattr(
        "polar_ble_tools.sdk_tools.verifier.verify_active_schemas",
        lambda *, cache: tmp_path / "schemas",
    )
    monkeypatch.setattr(
        "polar_ble_tools.rec.decoder_status",
        lambda *, cache: DecoderStatus(False, False, None, None, None, "not built"),
    )

    report = doctor(cache=cache)

    assert report.sdk.active_commit is None
    assert report.schemas.ready is True
    assert report.schemas.active_commit == commit


def test_apply_ftu_owns_session_and_applies_initial_settings(monkeypatch) -> None:
    calls: list[object] = []

    class Setup:
        async def do_first_time_use(self, profile: object) -> None:
            calls.append(("apply", profile))

        async def set_user_device_settings(self, patch: object) -> None:
            calls.append(("settings", patch))

    class Device:
        services = SimpleNamespace(setup=Setup())

    async def fake_run(_self, target, workflow):
        calls.append(("workflow", target.device_id))
        return await workflow(Device())

    monkeypatch.setattr(public_api.DeviceWorkflowRunner, "run", fake_run)
    patch = SimpleNamespace(has_changes=True)
    profile = SimpleNamespace(user_device_settings=patch)

    result = asyncio.run(apply_ftu("AA:BB:CC:DD:EE:FF", profile))

    assert result.ftu_applied and result.settings_updated
    assert calls == [("workflow", "AA:BB:CC:DD:EE:FF"), ("apply", profile), ("settings", patch)]


def test_recording_control_apis_use_one_workflow_and_immutable_results(
    monkeypatch, tmp_path
) -> None:
    calls: list[object] = []

    class Control:
        async def get_available_recording_types(self):
            return {PolarDeviceDataType.PPG, PolarDeviceDataType.ACC}

        async def get_recording_status(self):
            return {PolarDeviceDataType.ACC: True}

        async def request_recording_settings(self, data_type):
            assert data_type == PolarDeviceDataType.ACC
            return PmdSetting(settings={PmdSettingType.SAMPLE_RATE: {25, 50}})

        async def request_full_recording_settings(self, data_type):
            raise AssertionError(f"unexpected full request for {data_type}")

        async def start_recording(self, data_type, settings):
            calls.append(("start", data_type, settings.selected))

        async def stop_recording(self, data_type):
            calls.append(("stop", data_type))

        async def get_trigger_setup(self):
            return OfflineRecordingTrigger(
                mode=PmdOfflineRecTriggerMode.SYSTEM_START,
                trigger_features={PolarDeviceDataType.ACC: None},
            )

        async def set_trigger_setup(self, trigger):
            calls.append(("trigger", trigger.mode, trigger.trigger_features))

    class Offline:
        async def fetch_record(self, entry):
            calls.append(("fetch", entry.path))
            return SimpleNamespace(payload=b"recording")

    class Pftp:
        async def get_disk_space(self):
            return PftpDiskSpace(fragment_size=4, total_fragments=10, free_fragments=3)

    device = SimpleNamespace(
        services=SimpleNamespace(offline_control=Control(), offline=Offline(), pftp=Pftp())
    )

    async def fake_run(_self, target, workflow):
        calls.append(("workflow", target.device_id))
        return await workflow(device)

    monkeypatch.setattr(public_api.DeviceWorkflowRunner, "run", fake_run)

    types = asyncio.run(public_api.available_recording_types("aa-bb-cc-dd-ee-ff"))
    status = asyncio.run(public_api.recording_status("AA:BB:CC:DD:EE:FF"))
    settings = asyncio.run(public_api.recording_settings("AA:BB:CC:DD:EE:FF", "acc"))
    started = asyncio.run(
        public_api.start_recording("AA:BB:CC:DD:EE:FF", "acc", {"sample-rate": 25})
    )
    stopped = asyncio.run(public_api.stop_recording("AA:BB:CC:DD:EE:FF", "acc"))
    trigger = asyncio.run(public_api.offline_trigger("AA:BB:CC:DD:EE:FF"))
    updated = asyncio.run(
        public_api.update_offline_trigger(
            "AA:BB:CC:DD:EE:FF", "system-start", {"acc": {"sample_rate": 25}}
        )
    )
    disk_space = asyncio.run(public_api.device_disk_space("AA:BB:CC:DD:EE:FF"))
    fetched = asyncio.run(
        public_api.fetch_raw_recording(
            "AA:BB:CC:DD:EE:FF",
            "/U/0/20260725/R/112233/ACC0.REC",
            tmp_path / "ACC0.REC",
        )
    )

    assert types.to_jsonable()["types"] == ["ACC", "PPG"]
    assert status.to_jsonable()["active_by_type"] == {"ACC": True}
    assert settings.to_jsonable()["settings"] == {"SAMPLE_RATE": [25, 50]}
    assert started.active and not stopped.active
    assert trigger.to_jsonable()["mode"] == "system-start"
    assert updated.to_jsonable()["updated"]
    assert disk_space.to_jsonable()["used_bytes"] == 28
    assert fetched.output_path.read_bytes() == b"recording"
    with pytest.raises(TypeError):
        status.active_by_type[PolarDeviceDataType.ACC] = False
    assert calls.count(("workflow", "AA:BB:CC:DD:EE:FF")) == 9


def test_recording_control_validation_happens_before_workflow(monkeypatch, tmp_path) -> None:
    async def fail_run(*_args, **_kwargs):
        raise AssertionError("validation must run before a device workflow")

    monkeypatch.setattr(public_api.DeviceWorkflowRunner, "run", fail_run)

    with pytest.raises(ValueError, match="PPI exercise-start"):
        asyncio.run(
            public_api.update_offline_trigger("AA:BB:CC:DD:EE:FF", "exercise-start", {"ppi": None})
        )
    with pytest.raises(ValueError, match="invalid date or time"):
        asyncio.run(
            public_api.fetch_raw_recording(
                "AA:BB:CC:DD:EE:FF",
                "/U/0/20260230/R/112233/ACC0.REC",
                tmp_path / "ACC0.REC",
            )
        )
    output = tmp_path / "exists.REC"
    output.write_bytes(b"existing")
    with pytest.raises(FileExistsError):
        asyncio.run(
            public_api.fetch_raw_recording(
                "AA:BB:CC:DD:EE:FF",
                "/U/0/20260725/R/112233/ACC0.REC",
                output,
            )
        )
