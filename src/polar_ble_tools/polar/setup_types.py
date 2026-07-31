from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import IntEnum, StrEnum
from pathlib import Path
from typing import Any, ClassVar

PHYSICAL_DATA_PATH = "/U/0/S/PHYSDATA.BPB"
USER_IDENTIFIER_PATH = "/U/0/USERID.BPB"
USER_DEVICE_SETTINGS_PATH = "/U/0/S/UDEVSET.BPB"
NO_SUCH_FILE_OR_DIRECTORY = 103
MASTER_IDENTIFIER = (1 << 64) - 1
LOOP_GEN2_DEVICE_FAMILY = "POLAR_LOOP_GEN2"
VERITY_SENSE_DEVICE_FAMILY = "POLAR_VERITY_SENSE"


class SetupError(RuntimeError):
    """Base setup error."""


class SetupValidationError(SetupError, ValueError):
    """Raised when local FTU/setup input is invalid."""


class SetupStateError(SetupError):
    """Raised when existing device setup state is missing or malformed."""


class SetupUnsupportedError(SetupError):
    """Raised when a requested setup setting is not present on the device."""


class SetupDeviceResponseError(SetupError):
    """Raised when the device or PFTP transport rejects setup operations."""


class SetupPartialWriteError(SetupDeviceResponseError):
    """Raised after an FTU file write succeeds and a later setup operation fails."""


class Gender(StrEnum):
    MALE = "MALE"
    FEMALE = "FEMALE"

    @property
    def proto_value(self) -> int:
        return 1 if self is Gender.MALE else 2


class TypicalDay(StrEnum):
    MOSTLY_SITTING = "MOSTLY_SITTING"
    MOSTLY_STANDING = "MOSTLY_STANDING"
    MOSTLY_MOVING = "MOSTLY_MOVING"

    @property
    def proto_value(self) -> int:
        return {
            TypicalDay.MOSTLY_SITTING: 1,
            TypicalDay.MOSTLY_STANDING: 2,
            TypicalDay.MOSTLY_MOVING: 3,
        }[self]


class DeviceLocation(IntEnum):
    UNDEFINED = 0
    OTHER = 1
    WRIST_LEFT = 2
    WRIST_RIGHT = 3
    NECKLACE = 4
    CHEST = 5
    UPPER_BACK = 6
    FOOT_LEFT = 7
    FOOT_RIGHT = 8
    LOWER_ARM_LEFT = 9
    LOWER_ARM_RIGHT = 10
    UPPER_ARM_LEFT = 11
    UPPER_ARM_RIGHT = 12
    BIKE_MOUNT = 13

    @classmethod
    def from_name(cls, value: str) -> DeviceLocation:
        try:
            return cls[value.replace("-", "_").upper()]
        except KeyError as exc:
            raise SetupValidationError("device_location is not supported.") from exc


@dataclass(frozen=True)
class FtuProfile:
    device_family: ClassVar[str] = LOOP_GEN2_DEVICE_FAMILY

    gender: Gender
    birth_date: date
    height_cm: float
    weight_kg: float
    max_heart_rate_bpm: int
    resting_heart_rate_bpm: int
    vo2_max: int
    training_background: int
    typical_day: TypicalDay
    sleep_goal_minutes: int
    device_time: datetime = field(default_factory=lambda: datetime.now().astimezone())
    user_device_settings: UserDeviceSettingsPatch | None = None

    def __post_init__(self) -> None:
        _validate_range("height_cm", self.height_cm, 90.0, 240.0)
        _validate_range("weight_kg", self.weight_kg, 15.0, 300.0)
        _validate_range("max_heart_rate_bpm", self.max_heart_rate_bpm, 100, 240)
        _validate_range("resting_heart_rate_bpm", self.resting_heart_rate_bpm, 20, 120)
        _validate_range("vo2_max", self.vo2_max, 10, 95)
        if self.training_background not in {10, 20, 30, 40, 50, 60}:
            raise SetupValidationError("training_background must be one of 10, 20, 30, 40, 50, 60.")
        _validate_range("sleep_goal_minutes", self.sleep_goal_minutes, 300, 660)

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> FtuProfile:
        _validate_device_family(raw, expected=cls.device_family, required=False)
        return cls(
            gender=_parse_enum(Gender, raw, "gender"),
            birth_date=_parse_date(raw, "birth_date"),
            height_cm=_required_float(raw, "height_cm"),
            weight_kg=_required_float(raw, "weight_kg"),
            max_heart_rate_bpm=_required_int(raw, "max_heart_rate_bpm"),
            resting_heart_rate_bpm=_required_int(raw, "resting_heart_rate_bpm"),
            vo2_max=_required_int(raw, "vo2_max"),
            training_background=_required_int(raw, "training_background"),
            typical_day=_parse_enum(TypicalDay, raw, "typical_day"),
            sleep_goal_minutes=_required_int(raw, "sleep_goal_minutes"),
            device_time=_parse_datetime(raw["device_time"])
            if "device_time" in raw
            else datetime.now().astimezone(),
            user_device_settings=_parse_profile_user_device_settings(raw),
        )

    @classmethod
    def from_json_file(cls, path: str | Path) -> FtuProfile:
        return cls.from_mapping(_load_profile_mapping(path))


@dataclass(frozen=True)
class VeritySenseFtuProfile:
    device_location: DeviceLocation

    device_family: ClassVar[str] = VERITY_SENSE_DEVICE_FAMILY

    @property
    def user_device_settings(self) -> UserDeviceSettingsPatch:
        return UserDeviceSettingsPatch(device_location=self.device_location)

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> VeritySenseFtuProfile:
        _validate_device_family(raw, expected=cls.device_family, required=True)
        unsupported = sorted(set(raw) - {"device_family", "device_location"})
        if unsupported:
            raise SetupValidationError(
                "Verity Sense FTU profile contains unsupported fields: "
                + ", ".join(unsupported)
                + "."
            )
        location = _optional_device_location(raw, "device_location")
        if location is None:
            raise SetupValidationError("device_location is required.")
        return cls(device_location=location)

    @classmethod
    def from_json_file(cls, path: str | Path) -> VeritySenseFtuProfile:
        return cls.from_mapping(_load_profile_mapping(path))


FtuProfileInput = FtuProfile | VeritySenseFtuProfile


def load_ftu_profile(path: str | Path) -> FtuProfileInput:
    raw = _load_profile_mapping(path)
    family = _device_family(raw)
    if family is None or family == LOOP_GEN2_DEVICE_FAMILY:
        return FtuProfile.from_mapping(raw)
    if family == VERITY_SENSE_DEVICE_FAMILY:
        return VeritySenseFtuProfile.from_mapping(raw)
    raise SetupValidationError("device_family is not supported.")


@dataclass(frozen=True)
class PhysicalConfiguration:
    gender: Gender
    birth_date: date
    height_cm: float | None
    weight_kg: float | None
    max_heart_rate_bpm: int | None
    resting_heart_rate_bpm: int | None
    vo2_max: int | None
    training_background: int | None
    typical_day: TypicalDay | None
    sleep_goal_minutes: int | None
    last_modified: datetime | None

    def to_jsonable(self) -> dict[str, object]:
        return {
            "gender": self.gender.value,
            "birth_date": self.birth_date.isoformat(),
            "height_cm": self.height_cm,
            "weight_kg": self.weight_kg,
            "max_heart_rate_bpm": self.max_heart_rate_bpm,
            "resting_heart_rate_bpm": self.resting_heart_rate_bpm,
            "vo2_max": self.vo2_max,
            "training_background": self.training_background,
            "typical_day": self.typical_day.value if self.typical_day else None,
            "sleep_goal_minutes": self.sleep_goal_minutes,
            "last_modified": self.last_modified.isoformat() if self.last_modified else None,
        }


@dataclass(frozen=True)
class UserDeviceSettings:
    device_location: DeviceLocation | None = None
    usb_connection_mode: bool | None = None
    automatic_training_detection_mode: bool | None = None
    automatic_training_detection_sensitivity: int | None = None
    minimum_training_duration_seconds: int | None = None
    autos_files_enabled: bool | None = None
    telemetry_enabled: bool | None = None

    def to_jsonable(self) -> dict[str, object]:
        return {
            "device_location": self.device_location.name
            if self.device_location is not None
            else None,
            "usb_connection_mode": self.usb_connection_mode,
            "automatic_training_detection_mode": (self.automatic_training_detection_mode),
            "automatic_training_detection_sensitivity": (
                self.automatic_training_detection_sensitivity
            ),
            "minimum_training_duration_seconds": (self.minimum_training_duration_seconds),
            "autos_files_enabled": self.autos_files_enabled,
            "telemetry_enabled": self.telemetry_enabled,
        }


@dataclass(frozen=True)
class UserDeviceSettingsPatch:
    device_location: DeviceLocation | None = None
    usb_connection_mode: bool | None = None
    automatic_training_detection_mode: bool | None = None
    automatic_training_detection_sensitivity: int | None = None
    minimum_training_duration_seconds: int | None = None
    autos_files_enabled: bool | None = None

    def __post_init__(self) -> None:
        if self.automatic_training_detection_sensitivity is not None:
            _validate_range(
                "automatic_training_detection_sensitivity",
                self.automatic_training_detection_sensitivity,
                0,
                100,
            )
        if self.minimum_training_duration_seconds is not None:
            _validate_range(
                "minimum_training_duration_seconds",
                self.minimum_training_duration_seconds,
                0,
                24 * 60 * 60,
            )

    @property
    def has_changes(self) -> bool:
        return any(
            value is not None
            for value in (
                self.device_location,
                self.usb_connection_mode,
                self.automatic_training_detection_mode,
                self.automatic_training_detection_sensitivity,
                self.minimum_training_duration_seconds,
                self.autos_files_enabled,
            )
        )


_USER_DEVICE_SETTINGS_PROFILE_FIELDS = {
    "device_location",
    "usb_connection_mode",
    "automatic_training_detection_mode",
    "automatic_training_detection_sensitivity",
    "minimum_training_duration_seconds",
    "autos_files_enabled",
}


def _load_profile_mapping(path: str | Path) -> dict[str, Any]:
    try:
        raw = json.loads(Path(path).read_text())
    except OSError as exc:
        raise SetupValidationError("profile file could not be read.") from exc
    except json.JSONDecodeError as exc:
        raise SetupValidationError("profile file must contain valid JSON.") from exc
    if not isinstance(raw, dict):
        raise SetupValidationError("profile file must contain a JSON object.")
    return raw


def _device_family(raw: dict[str, Any]) -> str | None:
    value = raw.get("device_family")
    if value is None:
        return None
    if not isinstance(value, str):
        raise SetupValidationError("device_family must be a string.")
    return value.strip().replace("-", "_").upper()


def _validate_device_family(
    raw: dict[str, Any],
    *,
    expected: str,
    required: bool,
) -> None:
    family = _device_family(raw)
    if family is None:
        if required:
            raise SetupValidationError("device_family is required.")
        return
    if family != expected:
        raise SetupValidationError("device_family does not match the FTU profile type.")


def _parse_profile_user_device_settings(
    raw: dict[str, Any],
) -> UserDeviceSettingsPatch | None:
    embedded = raw.get("user_device_settings")
    top_level = {
        field_name: raw[field_name]
        for field_name in _USER_DEVICE_SETTINGS_PROFILE_FIELDS
        if field_name in raw
    }
    if embedded is None:
        settings = top_level
    else:
        if not isinstance(embedded, dict):
            raise SetupValidationError("user_device_settings must be a JSON object.")
        if top_level:
            raise SetupValidationError(
                "user-device settings must not be duplicated at profile top level."
            )
        settings = embedded
    if not settings:
        return None
    return UserDeviceSettingsPatch(
        device_location=_optional_device_location(settings, "device_location"),
        usb_connection_mode=_optional_bool(settings, "usb_connection_mode"),
        automatic_training_detection_mode=_optional_bool(
            settings,
            "automatic_training_detection_mode",
        ),
        automatic_training_detection_sensitivity=_optional_int(
            settings,
            "automatic_training_detection_sensitivity",
        ),
        minimum_training_duration_seconds=_optional_int(
            settings,
            "minimum_training_duration_seconds",
        ),
        autos_files_enabled=_optional_bool(settings, "autos_files_enabled"),
    )


def _validate_range(field_name: str, value: float | int, minimum: float, maximum: float) -> None:
    if value < minimum or value > maximum:
        raise SetupValidationError(f"{field_name} must be between {minimum:g} and {maximum:g}.")


def _required(raw: dict[str, Any], field_name: str) -> Any:
    if field_name not in raw:
        raise SetupValidationError(f"{field_name} is required.")
    return raw[field_name]


def _required_float(raw: dict[str, Any], field_name: str) -> float:
    value = _required(raw, field_name)
    if isinstance(value, bool):
        raise SetupValidationError(f"{field_name} must be a number.")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise SetupValidationError(f"{field_name} must be a number.") from exc


def _required_int(raw: dict[str, Any], field_name: str) -> int:
    value = _required(raw, field_name)
    if isinstance(value, bool):
        raise SetupValidationError(f"{field_name} must be an integer.")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdecimal():
        return int(value)
    raise SetupValidationError(f"{field_name} must be an integer.")


def _optional_int(raw: dict[str, Any], field_name: str) -> int | None:
    if field_name not in raw or raw[field_name] is None:
        return None
    value = raw[field_name]
    if isinstance(value, bool):
        raise SetupValidationError(f"{field_name} must be an integer.")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdecimal():
        return int(value)
    raise SetupValidationError(f"{field_name} must be an integer.")


def _optional_bool(raw: dict[str, Any], field_name: str) -> bool | None:
    if field_name not in raw or raw[field_name] is None:
        return None
    value = raw[field_name]
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "false"}:
            return normalized == "true"
    raise SetupValidationError(f"{field_name} must be a boolean.")


def _optional_device_location(
    raw: dict[str, Any],
    field_name: str,
) -> DeviceLocation | None:
    if field_name not in raw or raw[field_name] is None:
        return None
    value = raw[field_name]
    if not isinstance(value, str):
        raise SetupValidationError(f"{field_name} must be a string.")
    return DeviceLocation.from_name(value)


def _parse_enum(enum_type: type[StrEnum], raw: dict[str, Any], field_name: str) -> Any:
    value = _required(raw, field_name)
    if not isinstance(value, str):
        raise SetupValidationError(f"{field_name} must be a string.")
    try:
        return enum_type(value.replace("-", "_").upper())
    except ValueError as exc:
        raise SetupValidationError(f"{field_name} is not supported.") from exc


def _parse_date(raw: dict[str, Any], field_name: str) -> date:
    value = _required(raw, field_name)
    if not isinstance(value, str):
        raise SetupValidationError(f"{field_name} must be an ISO date.")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise SetupValidationError(f"{field_name} must use ISO date format YYYY-MM-DD.") from exc


def _parse_datetime(value: Any) -> datetime:
    if not isinstance(value, str):
        raise SetupValidationError("device_time must be an ISO datetime.")
    try:
        normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
        return datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise SetupValidationError("device_time must be an ISO datetime.") from exc
