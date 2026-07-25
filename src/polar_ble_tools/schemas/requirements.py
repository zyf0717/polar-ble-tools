from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SchemaFeatureRequirement:
    """Project-owned schema contract for one optional capability."""

    modules: tuple[str, ...]
    symbols: tuple[str, ...]


FEATURE_REQUIREMENTS: dict[str, SchemaFeatureRequirement] = {
    "setup": SchemaFeatureRequirement(
        modules=(
            "pftp_request_pb2",
            "types_pb2",
            "user_devset_pb2",
            "user_id_pb2",
            "user_physdata_pb2",
        ),
        symbols=(
            "PbDate",
            "protocol.PbPFtpSetLocalTimeParams",
            "protocol.PbPFtpSetSystemTimeParams",
            "PbSystemDateTime",
            "PbTime",
            "data.PbAutomaticMeasurementSettings",
            "data.PbAutomaticTrainingDetectionSettings",
            "data.PbSleepGoal",
            "data.PbUsbConnectionSettings",
            "data.PbUserBirthday",
            "data.PbUserDeviceSettings",
            "data.PbUserGender",
            "data.PbUserHeight",
            "data.PbUserHrAttribute",
            "data.PbUserIdentifier",
            "data.PbUserPhysData",
            "data.PbUserTrainingBackground",
            "data.PbUserTypicalDay",
            "data.PbUserVo2Max",
            "data.PbUserWeight",
        ),
    ),
    "passive": SchemaFeatureRequirement(
        modules=(
            "act_samples_pb2",
            "automatic_samples_pb2",
            "dailysummary_pb2",
            "nightly_recovery_pb2",
            "sleep_skin_temperature_result_pb2",
            "sleepanalysisresult_pb2",
            "temperature_measurement_period_pb2",
        ),
        symbols=(
            "data.PbActivitySamples",
            "data.PbAutomaticSampleSessions",
            "data.PbDailySummary",
            "data.PbNightlyRecoveryStatus",
            "data.PbSleepAnalysisResult",
            "data.PbSleepSkinTemperatureResult",
            "data.TemperatureMeasurementPeriod",
        ),
    ),
    "bpb": SchemaFeatureRequirement(
        modules=(
            "act_samples_pb2",
            "automatic_samples_pb2",
            "dailysummary_pb2",
            "device_pb2",
            "nightly_recovery_pb2",
            "sensor_data_log_pb2",
            "sleep_skin_temperature_result_pb2",
            "sleepanalysisresult_pb2",
            "temperature_measurement_period_pb2",
            "user_devset_pb2",
            "user_id_pb2",
            "user_physdata_pb2",
        ),
        symbols=(
            "data.PbDeviceInfo",
            "data.PbSensorDataLog",
            "data.PbUserDeviceSettings",
            "data.PbUserIdentifier",
            "data.PbUserPhysData",
        ),
    ),
}

# BPB dispatch resolves generated modules and message classes from the
# project-owned registry at runtime. The AST scanner cannot infer those strings,
# so each dynamic requirement remains named and reviewable rather than treating
# every schema declaration as implicitly used.
UNUSED_SCHEMA_MODULE_EXCEPTIONS: dict[str, str] = {
    "act_samples_pb2": "resolved dynamically by the BPB schema registry",
    "automatic_samples_pb2": "resolved dynamically by the BPB schema registry",
    "dailysummary_pb2": "resolved dynamically by the BPB schema registry",
    "device_pb2": "resolved dynamically by the BPB schema registry",
    "nightly_recovery_pb2": "resolved dynamically by the BPB schema registry",
    "sensor_data_log_pb2": "resolved dynamically by the BPB schema registry",
    "sleep_skin_temperature_result_pb2": "resolved dynamically by the BPB schema registry",
    "sleepanalysisresult_pb2": "resolved dynamically by the BPB schema registry",
    "temperature_measurement_period_pb2": "resolved dynamically by the BPB schema registry",
}

UNUSED_SCHEMA_SYMBOL_EXCEPTIONS: dict[str, str] = {
    "data.PbActivitySamples": "resolved dynamically by the BPB schema registry",
    "data.PbAutomaticSampleSessions": "resolved dynamically by the BPB schema registry",
    "data.PbDailySummary": "resolved dynamically by the BPB schema registry",
    "data.PbDeviceInfo": "resolved dynamically by the BPB schema registry",
    "data.PbNightlyRecoveryStatus": "resolved dynamically by the BPB schema registry",
    "data.PbSensorDataLog": "resolved dynamically by the BPB schema registry",
    "data.PbSleepAnalysisResult": "resolved dynamically by the BPB schema registry",
    "data.PbSleepSkinTemperatureResult": "resolved dynamically by the BPB schema registry",
    "data.TemperatureMeasurementPeriod": "resolved dynamically by the BPB schema registry",
}


def requirements_for(*features: str) -> SchemaFeatureRequirement:
    selected = features or tuple(FEATURE_REQUIREMENTS)
    unknown = sorted(set(selected) - FEATURE_REQUIREMENTS.keys())
    if unknown:
        raise ValueError(f"Unknown schema feature(s): {', '.join(unknown)}")
    return SchemaFeatureRequirement(
        modules=tuple(
            sorted(
                {module for feature in selected for module in FEATURE_REQUIREMENTS[feature].modules}
            )
        ),
        symbols=tuple(
            sorted(
                {symbol for feature in selected for symbol in FEATURE_REQUIREMENTS[feature].symbols}
            )
        ),
    )
