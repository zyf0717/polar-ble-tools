from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from google.protobuf.message import DecodeError, EncodeError

from polar_ble_tools.polar.setup_types import (
    MASTER_IDENTIFIER,
    PHYSICAL_DATA_PATH,
    USER_IDENTIFIER_PATH,
    DeviceLocation,
    FtuProfile,
    Gender,
    PhysicalConfiguration,
    SetupStateError,
    SetupUnsupportedError,
    TypicalDay,
    UserDeviceSettings,
    UserDeviceSettingsPatch,
)
from polar_ble_tools.schemas import require_modules


class _GeneratedModuleProxy:
    def __init__(self, name: str) -> None:
        self._name = name

    def __getattr__(self, attribute: str) -> Any:
        return getattr(getattr(require_modules(self._name), self._name), attribute)


pftp_request_pb2 = _GeneratedModuleProxy("pftp_request_pb2")
types_pb2 = _GeneratedModuleProxy("types_pb2")
user_devset_pb2 = _GeneratedModuleProxy("user_devset_pb2")
user_id_pb2 = _GeneratedModuleProxy("user_id_pb2")
user_physdata_pb2 = _GeneratedModuleProxy("user_physdata_pb2")


def build_physical_data_payload(profile: FtuProfile) -> bytes:
    last_modified = build_system_datetime(profile.device_time)
    birthday = user_physdata_pb2.PbUserBirthday(
        value=_pb_date(profile.birth_date),
        last_modified=last_modified,
    )
    phys_data = user_physdata_pb2.PbUserPhysData(
        birthday=birthday,
        gender=user_physdata_pb2.PbUserGender(
            value=profile.gender.proto_value,
            last_modified=last_modified,
        ),
        weight=user_physdata_pb2.PbUserWeight(
            value=profile.weight_kg,
            last_modified=last_modified,
        ),
        height=user_physdata_pb2.PbUserHeight(
            value=profile.height_cm,
            last_modified=last_modified,
        ),
        maximum_heartrate=user_physdata_pb2.PbUserHrAttribute(
            value=profile.max_heart_rate_bpm,
            last_modified=last_modified,
        ),
        resting_heartrate=user_physdata_pb2.PbUserHrAttribute(
            value=profile.resting_heart_rate_bpm,
            last_modified=last_modified,
        ),
        training_background=user_physdata_pb2.PbUserTrainingBackground(
            value=profile.training_background,
            last_modified=last_modified,
        ),
        vo2max=user_physdata_pb2.PbUserVo2Max(
            value=profile.vo2_max,
            last_modified=last_modified,
        ),
        typical_day=user_physdata_pb2.PbUserTypicalDay(
            value=profile.typical_day.proto_value,
            last_modified=last_modified,
        ),
        sleep_goal=user_physdata_pb2.PbSleepGoal(
            sleep_goal_minutes=profile.sleep_goal_minutes,
            last_modified=last_modified,
        ),
        last_modified=last_modified,
    )
    _assert_initialized(phys_data, "physical data")
    return phys_data.SerializeToString()


def build_user_identifier_payload(device_time: datetime | None = None) -> bytes:
    identifier = user_id_pb2.PbUserIdentifier(
        master_identifier=MASTER_IDENTIFIER,
        user_id_last_modified=build_system_datetime(device_time),
    )
    return identifier.SerializeToString()


def is_user_identifier_present(data: bytes) -> bool:
    identifier = user_id_pb2.PbUserIdentifier()
    try:
        identifier.ParseFromString(data)
    except DecodeError as exc:
        raise SetupStateError("USERID.BPB is not a valid user identifier.") from exc
    return identifier.HasField("master_identifier")


def build_system_time_payload(device_time: datetime) -> bytes:
    message = pftp_request_pb2.PbPFtpSetSystemTimeParams()
    message.date.CopyFrom(_pb_date(_as_aware(device_time).astimezone(timezone.utc).date()))
    message.time.CopyFrom(_pb_time(_as_aware(device_time).astimezone(timezone.utc)))
    message.trusted = True
    return message.SerializeToString()


def build_local_time_payload(device_time: datetime) -> bytes:
    aware = _as_aware(device_time)
    message = pftp_request_pb2.PbPFtpSetLocalTimeParams()
    message.date.CopyFrom(_pb_date(aware.date()))
    message.time.CopyFrom(_pb_time(aware))
    offset = aware.utcoffset()
    message.tz_offset = int(offset.total_seconds() // 60) if offset else 0
    return message.SerializeToString()


def parse_local_time_payload(data: bytes) -> datetime:
    message = pftp_request_pb2.PbPFtpSetLocalTimeParams()
    try:
        message.ParseFromString(data)
    except DecodeError as exc:
        raise SetupStateError("Local time response is not valid local-time data.") from exc
    if not message.IsInitialized():
        raise SetupStateError("Local time response is missing required fields.")
    try:
        local_timezone = timezone(timedelta(minutes=message.tz_offset))
        return datetime(
            message.date.year,
            message.date.month,
            message.date.day,
            message.time.hour,
            message.time.minute,
            message.time.seconds,
            message.time.millis * 1000,
            tzinfo=local_timezone,
        )
    except ValueError as exc:
        raise SetupStateError(
            "Local time response contains an invalid date, time, or offset."
        ) from exc


def build_system_datetime(device_time: datetime | None = None) -> types_pb2.PbSystemDateTime:
    aware = _as_aware(device_time or datetime.now().astimezone()).astimezone(timezone.utc)
    return types_pb2.PbSystemDateTime(
        date=_pb_date(aware.date()),
        time=_pb_time(aware),
        trusted=True,
    )


def parse_physical_configuration(data: bytes) -> PhysicalConfiguration:
    phys_data = user_physdata_pb2.PbUserPhysData()
    try:
        phys_data.ParseFromString(data)
    except DecodeError as exc:
        raise SetupStateError("PHYSDATA.BPB is not valid physical data.") from exc
    if not phys_data.HasField("birthday") or not phys_data.HasField("gender"):
        raise SetupStateError("PHYSDATA.BPB is missing required FTU fields.")
    return PhysicalConfiguration(
        gender=_gender_from_value(phys_data.gender.value),
        birth_date=date(
            phys_data.birthday.value.year,
            phys_data.birthday.value.month,
            phys_data.birthday.value.day,
        ),
        height_cm=phys_data.height.value if phys_data.HasField("height") else None,
        weight_kg=phys_data.weight.value if phys_data.HasField("weight") else None,
        max_heart_rate_bpm=phys_data.maximum_heartrate.value
        if phys_data.HasField("maximum_heartrate")
        else None,
        resting_heart_rate_bpm=phys_data.resting_heartrate.value
        if phys_data.HasField("resting_heartrate")
        else None,
        vo2_max=phys_data.vo2max.value if phys_data.HasField("vo2max") else None,
        training_background=phys_data.training_background.value
        if phys_data.HasField("training_background")
        else None,
        typical_day=_typical_day_from_value(phys_data.typical_day.value)
        if phys_data.HasField("typical_day")
        else None,
        sleep_goal_minutes=phys_data.sleep_goal.sleep_goal_minutes
        if phys_data.HasField("sleep_goal") and phys_data.sleep_goal.HasField("sleep_goal_minutes")
        else None,
        last_modified=_datetime_from_system(phys_data.last_modified)
        if phys_data.HasField("last_modified")
        else None,
    )


def parse_user_device_settings(data: bytes) -> UserDeviceSettings:
    settings = _parse_user_device_settings_proto(data)
    general = settings.general_settings if settings.HasField("general_settings") else None
    automatic = (
        settings.automatic_measurement_settings
        if settings.HasField("automatic_measurement_settings")
        else None
    )
    training = (
        automatic.automatic_training_detection_settings
        if automatic is not None and automatic.HasField("automatic_training_detection_settings")
        else None
    )
    ohr = (
        automatic.automatic_ohr_measurement
        if automatic is not None and automatic.HasField("automatic_ohr_measurement")
        else None
    )
    usb = settings.usb_connection_settings if settings.HasField("usb_connection_settings") else None
    telemetry = settings.telemetry_settings if settings.HasField("telemetry_settings") else None
    return UserDeviceSettings(
        device_location=_device_location_from_value(general.device_location)
        if general is not None and general.HasField("device_location")
        else None,
        usb_connection_mode=usb.mode == user_devset_pb2.PbUsbConnectionSettings.ON
        if usb is not None and usb.HasField("mode")
        else None,
        automatic_training_detection_mode=(
            training.state == user_devset_pb2.PbAutomaticTrainingDetectionSettings.ON
        )
        if training is not None and training.HasField("state")
        else None,
        automatic_training_detection_sensitivity=training.sensitivity
        if training is not None and training.HasField("sensitivity")
        else None,
        minimum_training_duration_seconds=training.minimum_training_duration_seconds
        if training is not None and training.HasField("minimum_training_duration_seconds")
        else None,
        autos_files_enabled=ohr.state != user_devset_pb2.PbAutomaticMeasurementSettings.OFF
        if ohr is not None and ohr.HasField("state")
        else None,
        telemetry_enabled=telemetry.telemetry_enabled
        if telemetry is not None and telemetry.HasField("telemetry_enabled")
        else None,
    )


def apply_user_device_settings_patch(
    data: bytes,
    patch: UserDeviceSettingsPatch,
    *,
    modified_at: datetime | None = None,
) -> bytes:
    settings = _parse_user_device_settings_proto(data)
    if patch.device_location is not None:
        _require_field(settings, "general_settings", "general_settings")
        _require_field(settings.general_settings, "device_location", "device_location")
        settings.general_settings.device_location = int(patch.device_location)
    if patch.usb_connection_mode is not None:
        _require_field(settings, "usb_connection_settings", "usb_connection_mode")
        _require_field(settings.usb_connection_settings, "mode", "usb_connection_mode")
        settings.usb_connection_settings.mode = (
            user_devset_pb2.PbUsbConnectionSettings.ON
            if patch.usb_connection_mode
            else user_devset_pb2.PbUsbConnectionSettings.OFF
        )
    automatic_requested = any(
        value is not None
        for value in (
            patch.automatic_training_detection_mode,
            patch.automatic_training_detection_sensitivity,
            patch.minimum_training_duration_seconds,
            patch.autos_files_enabled,
        )
    )
    if automatic_requested:
        _require_field(
            settings,
            "automatic_measurement_settings",
            "automatic_measurement_settings",
        )
    automatic = settings.automatic_measurement_settings
    if patch.autos_files_enabled is not None:
        _require_field(automatic, "automatic_ohr_measurement", "autos_files")
        _require_field(automatic.automatic_ohr_measurement, "state", "autos_files")
        automatic.automatic_ohr_measurement.state = (
            user_devset_pb2.PbAutomaticMeasurementSettings.ALWAYS_ON
            if patch.autos_files_enabled
            else user_devset_pb2.PbAutomaticMeasurementSettings.OFF
        )
    training_requested = any(
        value is not None
        for value in (
            patch.automatic_training_detection_mode,
            patch.automatic_training_detection_sensitivity,
            patch.minimum_training_duration_seconds,
        )
    )
    if training_requested:
        _require_field(
            automatic,
            "automatic_training_detection_settings",
            "automatic_training_detection_settings",
        )
    training = automatic.automatic_training_detection_settings
    if patch.automatic_training_detection_mode is not None:
        _require_field(training, "state", "automatic_training_detection_mode")
        training.state = (
            user_devset_pb2.PbAutomaticTrainingDetectionSettings.ON
            if patch.automatic_training_detection_mode
            else user_devset_pb2.PbAutomaticTrainingDetectionSettings.OFF
        )
    if patch.automatic_training_detection_sensitivity is not None:
        _require_field(
            training,
            "sensitivity",
            "automatic_training_detection_sensitivity",
        )
        training.sensitivity = patch.automatic_training_detection_sensitivity
    if patch.minimum_training_duration_seconds is not None:
        _require_field(
            training,
            "minimum_training_duration_seconds",
            "minimum_training_duration_seconds",
        )
        training.minimum_training_duration_seconds = patch.minimum_training_duration_seconds
    settings.last_modified.CopyFrom(build_system_datetime(modified_at))
    _assert_initialized(settings, "user-device settings")
    return settings.SerializeToString()


def profile_payload_sizes(profile: FtuProfile) -> dict[str, int]:
    return {
        PHYSICAL_DATA_PATH: len(build_physical_data_payload(profile)),
        USER_IDENTIFIER_PATH: len(build_user_identifier_payload()),
        "SET_SYSTEM_TIME": len(build_system_time_payload(profile.device_time)),
        "SET_LOCAL_TIME": len(build_local_time_payload(profile.device_time)),
    }


def _gender_from_value(value: int) -> Gender:
    if value == user_physdata_pb2.PbUserGender.MALE:
        return Gender.MALE
    if value == user_physdata_pb2.PbUserGender.FEMALE:
        return Gender.FEMALE
    raise SetupStateError("PHYSDATA.BPB contains an unknown gender value.")


def _device_location_from_value(value: int) -> DeviceLocation:
    try:
        return DeviceLocation(value)
    except ValueError as exc:
        raise SetupStateError("UDEVSET.BPB contains an unknown device_location value.") from exc


def _parse_user_device_settings_proto(data: bytes) -> user_devset_pb2.PbUserDeviceSettings:
    settings = user_devset_pb2.PbUserDeviceSettings()
    try:
        settings.ParseFromString(data)
    except DecodeError as exc:
        raise SetupStateError("UDEVSET.BPB is not valid user-device settings.") from exc
    if not settings.HasField("general_settings"):
        raise SetupStateError("UDEVSET.BPB is missing general settings.")
    if not settings.HasField("last_modified"):
        raise SetupStateError("UDEVSET.BPB is missing last_modified.")
    return settings


def _require_field(message: Any, field_name: str, setting_name: str) -> None:
    if not message.HasField(field_name):
        raise SetupUnsupportedError(f"{setting_name} is not present on this device.")


def _assert_initialized(message: Any, name: str) -> None:
    try:
        message.SerializeToString()
    except EncodeError as exc:
        raise SetupStateError(f"{name} protobuf is missing required fields.") from exc


def _as_aware(value: datetime) -> datetime:
    return value.astimezone() if value.tzinfo is None else value


def _pb_date(value: date) -> types_pb2.PbDate:
    return types_pb2.PbDate(year=value.year, month=value.month, day=value.day)


def _pb_time(value: datetime) -> types_pb2.PbTime:
    return types_pb2.PbTime(
        hour=value.hour,
        minute=value.minute,
        seconds=value.second,
        millis=value.microsecond // 1000,
    )


def _datetime_from_system(value: types_pb2.PbSystemDateTime) -> datetime:
    return datetime(
        value.date.year,
        value.date.month,
        value.date.day,
        value.time.hour,
        value.time.minute,
        value.time.seconds,
        value.time.millis * 1000,
        tzinfo=timezone.utc,
    )


def _typical_day_from_value(value: int) -> TypicalDay:
    for typical_day in TypicalDay:
        if typical_day.proto_value == value:
            return typical_day
    raise SetupStateError("PHYSDATA.BPB contains an unknown typical_day value.")
