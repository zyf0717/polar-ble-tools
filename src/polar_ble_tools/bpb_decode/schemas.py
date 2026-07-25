from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from google.protobuf.message import Message

from polar_ble_tools.bpb_decode.paths import normalize_device_path
from polar_ble_tools.schemas import require_modules


@dataclass(frozen=True)
class BpbSchema:
    schema_id: str
    module_name: str
    class_name: str
    exact_paths: tuple[str, ...] = ()
    path_patterns: tuple[re.Pattern[str], ...] = ()
    filename_pattern: re.Pattern[str] | None = None

    @property
    def message_class(self) -> type[Message]:
        module = getattr(require_modules(self.module_name), self.module_name)
        return getattr(module, self.class_name)

    @property
    def message_type(self) -> str:
        return self.message_class.DESCRIPTOR.full_name

    def matches(self, device_path: str | None, filename: str, *, mode: str) -> bool:
        if mode == "exact":
            return device_path is not None and normalize_device_path(device_path).upper() in {
                normalize_device_path(path).upper() for path in self.exact_paths
            }
        if mode == "pattern":
            return device_path is not None and any(
                pattern.fullmatch(normalize_device_path(device_path).upper())
                for pattern in self.path_patterns
            )
        return (
            self.filename_pattern is not None
            and self.filename_pattern.fullmatch(filename) is not None
        )


def _path(raw: str) -> re.Pattern[str]:
    return re.compile(raw, re.IGNORECASE)


def _filename(raw: str) -> re.Pattern[str]:
    return re.compile(raw, re.IGNORECASE)


BPB_SCHEMAS: tuple[BpbSchema, ...] = (
    BpbSchema(
        "device_info",
        "device_pb2",
        "PbDeviceInfo",
        exact_paths=("/DEVICE.BPB",),
        filename_pattern=_filename(r"DEVICE\.BPB"),
    ),
    BpbSchema(
        "sensor_data_log",
        "sensor_data_log_pb2",
        "PbSensorDataLog",
        exact_paths=("/SDLOGS.BPB",),
        filename_pattern=_filename(r"SDLOGS\.BPB"),
    ),
    BpbSchema(
        "activity_samples",
        "act_samples_pb2",
        "PbActivitySamples",
        path_patterns=(_path(r"/U/\d+/\d{8}/ACT/ASAMPL\d+\.BPB"),),
        filename_pattern=_filename(r"ASAMPL\d+\.BPB"),
    ),
    BpbSchema(
        "daily_summary",
        "dailysummary_pb2",
        "PbDailySummary",
        path_patterns=(_path(r"/U/\d+/\d{8}/DSUM/DSUM\.BPB"),),
        filename_pattern=_filename(r"DSUM\.BPB"),
    ),
    BpbSchema(
        "automatic_sample_sessions",
        "automatic_samples_pb2",
        "PbAutomaticSampleSessions",
        path_patterns=(_path(r"/U/\d+/AUTOS/AUTOS\d{3}\.BPB"),),
        filename_pattern=_filename(r"AUTOS\d{3}\.BPB"),
    ),
    BpbSchema(
        "sleep_analysis",
        "sleepanalysisresult_pb2",
        "PbSleepAnalysisResult",
        path_patterns=(_path(r"/U/\d+/\d{8}/SLEEP/SLEEPRES\.BPB"),),
        filename_pattern=_filename(r"SLEEPRES\.BPB"),
    ),
    BpbSchema(
        "sleep_skin_temperature_result",
        "sleep_skin_temperature_result_pb2",
        "PbSleepSkinTemperatureResult",
        path_patterns=(_path(r"/U/\d+/\d{8}/NSTRESUL/NSTRCONT\.BPB"),),
        filename_pattern=_filename(r"NSTRCONT\.BPB"),
    ),
    BpbSchema(
        "nightly_recovery",
        "nightly_recovery_pb2",
        "PbNightlyRecoveryStatus",
        path_patterns=(_path(r"/U/\d+/\d{8}/NR/NR\.BPB"),),
        filename_pattern=_filename(r"NR\.BPB"),
    ),
    BpbSchema(
        "skin_temperature_period",
        "temperature_measurement_period_pb2",
        "TemperatureMeasurementPeriod",
        path_patterns=(_path(r"/U/\d+/\d{8}/SKINTEMP/TEMPCONT\.BPB"),),
    ),
    BpbSchema(
        "user_phys_data",
        "user_physdata_pb2",
        "PbUserPhysData",
        path_patterns=(_path(r"/U/\d+/S/PHYSDATA\.BPB"),),
        filename_pattern=_filename(r"PHYSDATA\.BPB"),
    ),
    BpbSchema(
        "user_device_settings",
        "user_devset_pb2",
        "PbUserDeviceSettings",
        path_patterns=(_path(r"/U/\d+/S/UDEVSET\.BPB"),),
        filename_pattern=_filename(r"UDEVSET\.BPB"),
    ),
    BpbSchema(
        "user_identifier",
        "user_id_pb2",
        "PbUserIdentifier",
        path_patterns=(_path(r"/U/\d+/USERID\.BPB"),),
        filename_pattern=_filename(r"USERID\.BPB"),
    ),
)


def schema_for_bpb(*, device_path: str | None, local_path: str | Path) -> BpbSchema | None:
    normalized = normalize_device_path(device_path) if device_path else None
    filename = Path(local_path).name.upper()
    for mode in ("exact", "pattern", "filename"):
        for schema in BPB_SCHEMAS:
            if schema.matches(normalized, filename, mode=mode):
                return schema
    return None
