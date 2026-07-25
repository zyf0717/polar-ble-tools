from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, StrEnum

DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_STOP_POLL_INTERVAL_SECONDS = 0.2
DEFAULT_STOP_TIMEOUT_SECONDS = 5.0
CONTROL_POINT_RESPONSE_CODE = 0xF0
MEASUREMENT_TYPE_MASK = 0x3F
MEASUREMENT_STATUS_MASK = 0xC0


class PmdError(RuntimeError):
    """Base PMD error."""


class PmdProtocolError(PmdError):
    """Raised when PMD packets or local PMD command data are invalid."""


class PmdTimeoutError(PmdError):
    """Raised when a PMD response or status transition times out."""


class PmdUnsupportedOperation(PmdError):
    """Raised when the SDK marks an operation as unsupported."""


class PmdResponseError(PmdError):
    def __init__(
        self,
        message: str,
        *,
        command: PmdControlPointCommand | None,
        response_code: PmdResponseCode,
        measurement_type: int | None = None,
    ) -> None:
        self.command = command
        self.response_code = response_code
        self.measurement_type = measurement_type
        suffix = f"{response_code.name}({int(response_code)})"
        if command is not None:
            suffix = f"{command.name}: {suffix}"
        super().__init__(f"{message}: {suffix}")


class PolarDeviceDataType(StrEnum):
    ECG = "ECG"
    ACC = "ACC"
    PPG = "PPG"
    PPI = "PPI"
    GYRO = "GYRO"
    MAGNETOMETER = "MAGNETOMETER"
    LOCATION = "LOCATION"
    PRESSURE = "PRESSURE"
    TEMPERATURE = "TEMPERATURE"
    SKIN_TEMPERATURE = "SKIN_TEMPERATURE"
    HR = "HR"


class PmdMeasurementType(IntEnum):
    ECG = 0x00
    PPG = 0x01
    ACC = 0x02
    PPI = 0x03
    GYRO = 0x05
    MAGNETOMETER = 0x06
    SKIN_TEMP = 0x07
    SDK_MODE = 0x09
    LOCATION = 0x0A
    PRESSURE = 0x0B
    TEMPERATURE = 0x0C
    OFFLINE_RECORDING = 0x0D
    OFFLINE_HR = 0x0E
    DERIVED_MEASUREMENT = 0x0F
    UNKNOWN_TYPE = 0x3F

    @classmethod
    def from_status_byte(cls, value: int) -> PmdMeasurementType:
        try:
            return cls(value & MEASUREMENT_TYPE_MASK)
        except ValueError:
            return cls.UNKNOWN_TYPE

    @property
    def is_data_type(self) -> bool:
        return self not in {
            PmdMeasurementType.SDK_MODE,
            PmdMeasurementType.OFFLINE_RECORDING,
            PmdMeasurementType.DERIVED_MEASUREMENT,
            PmdMeasurementType.UNKNOWN_TYPE,
        }


class PmdRecordingType(IntEnum):
    ONLINE = 0
    OFFLINE = 1

    @property
    def bitfield(self) -> int:
        return int(self) << 7


class PmdActiveMeasurement(IntEnum):
    NO_ACTIVE_MEASUREMENT = 0
    ONLINE_MEASUREMENT_ACTIVE = 1
    OFFLINE_MEASUREMENT_ACTIVE = 2
    ONLINE_AND_OFFLINE_ACTIVE = 3
    UNKNOWN_MEASUREMENT_STATUS = -1

    @classmethod
    def from_status_byte(cls, value: int) -> PmdActiveMeasurement:
        try:
            return cls((value & MEASUREMENT_STATUS_MASK) >> 6)
        except ValueError:
            return cls.UNKNOWN_MEASUREMENT_STATUS

    @property
    def is_offline_active(self) -> bool:
        return self in {
            PmdActiveMeasurement.OFFLINE_MEASUREMENT_ACTIVE,
            PmdActiveMeasurement.ONLINE_AND_OFFLINE_ACTIVE,
        }


class PmdControlPointCommand(IntEnum):
    NULL_ITEM = 0
    GET_MEASUREMENT_SETTINGS = 1
    REQUEST_MEASUREMENT_START = 2
    STOP_MEASUREMENT = 3
    GET_SDK_MODE_MEASUREMENT_SETTINGS = 4
    GET_MEASUREMENT_STATUS = 5
    GET_SDK_MODE_STATUS = 6
    GET_OFFLINE_RECORDING_TRIGGER_STATUS = 7
    SET_OFFLINE_RECORDING_TRIGGER_MODE = 8
    SET_OFFLINE_RECORDING_TRIGGER_SETTINGS = 9
    GET_DERIVED_MEASUREMENT_SETTINGS_GROUP = 0x0A


class PmdResponseCode(IntEnum):
    SUCCESS = 0
    ERROR_INVALID_OP_CODE = 1
    ERROR_INVALID_MEASUREMENT_TYPE = 2
    ERROR_NOT_SUPPORTED = 3
    ERROR_INVALID_LENGTH = 4
    ERROR_INVALID_PARAMETER = 5
    ERROR_ALREADY_IN_STATE = 6
    ERROR_INVALID_RESOLUTION = 7
    ERROR_INVALID_SAMPLE_RATE = 8
    ERROR_INVALID_RANGE = 9
    ERROR_INVALID_MTU = 10
    ERROR_INVALID_NUMBER_OF_CHANNELS = 11
    ERROR_INVALID_STATE = 12
    ERROR_DEVICE_IN_CHARGER = 13
    ERROR_DISK_FULL = 14
    ERROR_INVALID_SOURCE_MEASUREMENT_TYPE = 15
    ERROR_INVALID_SOURCE_MEASUREMENT_RATE = 16
    ERROR_INVALID_DERIVED_MEASUREMENT_SETTINGS_GROUP = 17
    ERROR_INVALID_DERIVED_MEASUREMENT_METHOD = 18
    UNKNOWN_ERROR = -1

    @classmethod
    def from_byte(cls, value: int) -> PmdResponseCode:
        try:
            return cls(value)
        except ValueError:
            return cls.UNKNOWN_ERROR


class PmdSettingType(IntEnum):
    SAMPLE_RATE = 0
    RESOLUTION = 1
    RANGE = 2
    RANGE_MILLIUNIT = 3
    CHANNELS = 4
    FACTOR = 5
    SECURITY = 6
    DERIVED_MEASUREMENT_METHOD = 7
    SOURCE_MEASUREMENT_TYPE = 8
    SOURCE_MEASUREMENT_SAMPLE_RATE = 9
    SOURCE_MEASUREMENT_RANGE = 10
    DERIVED_MEASUREMENT_TIME_WINDOW = 11
    DERIVED_MEASUREMENT_SETTINGS_GROUP_ID = 12

    @classmethod
    def from_name(cls, name: str) -> PmdSettingType:
        normalized = name.replace("-", "_").upper()
        try:
            return cls[normalized]
        except KeyError as exc:
            raise PmdProtocolError(f"Unknown PMD setting type: {name}") from exc


SETTING_FIELD_SIZES: dict[PmdSettingType, int] = {
    PmdSettingType.SAMPLE_RATE: 2,
    PmdSettingType.RESOLUTION: 2,
    PmdSettingType.RANGE: 2,
    PmdSettingType.RANGE_MILLIUNIT: 4,
    PmdSettingType.CHANNELS: 1,
    PmdSettingType.FACTOR: 4,
    PmdSettingType.SECURITY: 16,
    PmdSettingType.DERIVED_MEASUREMENT_METHOD: 1,
    PmdSettingType.SOURCE_MEASUREMENT_TYPE: 1,
    PmdSettingType.SOURCE_MEASUREMENT_SAMPLE_RATE: 2,
    PmdSettingType.SOURCE_MEASUREMENT_RANGE: 4,
    PmdSettingType.DERIVED_MEASUREMENT_TIME_WINDOW: 4,
    PmdSettingType.DERIVED_MEASUREMENT_SETTINGS_GROUP_ID: 1,
}
RESPONSE_ONLY_SETTING_TYPES = {
    PmdSettingType.FACTOR,
    PmdSettingType.SOURCE_MEASUREMENT_RANGE,
}


@dataclass
class PmdSetting:
    settings: dict[PmdSettingType, set[int]] = field(default_factory=dict)
    selected: dict[PmdSettingType, int] = field(default_factory=dict)

    @classmethod
    def parse(cls, data: bytes) -> PmdSetting:
        settings: dict[PmdSettingType, set[int]] = {}
        offset = 0
        while offset < len(data):
            if offset + 2 > len(data):
                raise PmdProtocolError("Broken PMD settings data.")
            try:
                setting_type = PmdSettingType(data[offset])
            except ValueError as exc:
                raise PmdProtocolError(f"Unknown PMD setting type id: {data[offset]}") from exc
            offset += 1
            count = data[offset]
            offset += 1
            field_size = SETTING_FIELD_SIZES[setting_type]
            values: set[int] = set()
            for _ in range(count):
                if offset + field_size > len(data):
                    raise PmdProtocolError("Broken PMD settings data.")
                values.add(int.from_bytes(data[offset : offset + field_size], "little"))
                offset += field_size
            settings[setting_type] = values
        return cls(settings=settings)

    @classmethod
    def from_selected(
        cls,
        selected: dict[PmdSettingType | str, int] | None = None,
    ) -> PmdSetting:
        if not selected:
            return cls()
        parsed: dict[PmdSettingType, int] = {}
        for key, value in selected.items():
            setting_type = PmdSettingType.from_name(key) if isinstance(key, str) else key
            parsed[setting_type] = int(value)
        return cls(selected=parsed)

    def serialize_selected(self) -> bytes:
        payload = bytearray()
        for setting_type, value in self.selected.items():
            if setting_type in RESPONSE_ONLY_SETTING_TYPES:
                continue
            if setting_type == PmdSettingType.DERIVED_MEASUREMENT_METHOD:
                method_ids = [bit for bit in range(16) if (value >> bit) & 1]
                if not method_ids:
                    continue
                payload.extend((int(setting_type), len(method_ids)))
                payload.extend(method_ids)
                continue
            field_size = SETTING_FIELD_SIZES[setting_type]
            max_value = (1 << (field_size * 8)) - 1
            if value < 0 or value > max_value:
                raise PmdProtocolError(
                    f"PMD setting {setting_type.name} out of range for {field_size} bytes: {value}"
                )
            payload.extend((int(setting_type), 1))
            payload.extend(value.to_bytes(field_size, "little"))
        return bytes(payload)

    def update_selected_from_start_response(self, data: bytes) -> None:
        parsed = PmdSetting.parse(data)
        factor = parsed.settings.get(PmdSettingType.FACTOR)
        if factor:
            self.selected[PmdSettingType.FACTOR] = next(iter(factor))

    def to_jsonable(self) -> dict[str, object]:
        if self.settings:
            return {"settings": {key.name: sorted(values) for key, values in self.settings.items()}}
        return {"selected": {key.name: value for key, value in self.selected.items()}}


class PmdSecurityStrategy(IntEnum):
    NONE = 0
    XOR = 1
    AES128 = 2
    AES256 = 3


@dataclass(frozen=True)
class PmdSecret:
    strategy: PmdSecurityStrategy
    key: bytes = b""

    def __post_init__(self) -> None:
        required_sizes = {
            PmdSecurityStrategy.NONE: 0,
            PmdSecurityStrategy.AES128: 16,
            PmdSecurityStrategy.AES256: 32,
        }
        required = required_sizes.get(self.strategy)
        if required is not None and len(self.key) != required:
            raise PmdProtocolError(
                f"{self.strategy.name} key must be {required} bytes, got {len(self.key)}"
            )
        if self.strategy == PmdSecurityStrategy.XOR and not self.key:
            raise PmdProtocolError("XOR key must not be empty.")

    def serialize(self) -> bytes:
        return (
            bytes(
                (
                    int(PmdSettingType.SECURITY),
                    1,
                    int(self.strategy),
                )
            )
            + self.key
        )

    def decrypt(self, data: bytes) -> bytes:
        if self.strategy == PmdSecurityStrategy.NONE:
            return data
        if self.strategy == PmdSecurityStrategy.XOR:
            key = self.key[0]
            return bytes(value ^ key for value in data)
        if len(data) % 16 != 0:
            raise PmdProtocolError(
                f"{self.strategy.name} encrypted data must be a multiple of 16 bytes."
            )
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

        decryptor = Cipher(
            algorithms.AES(self.key),
            modes.ECB(),
        ).decryptor()
        return decryptor.update(data) + decryptor.finalize()


class PmdOfflineRecTriggerMode(IntEnum):
    DISABLED = 0
    SYSTEM_START = 1
    EXERCISE_START = 2


class PmdOfflineRecTriggerStatus(IntEnum):
    DISABLED = 0
    ENABLED = 1


@dataclass(frozen=True)
class PmdOfflineTrigger:
    mode: PmdOfflineRecTriggerMode
    triggers: dict[PmdMeasurementType, tuple[PmdOfflineRecTriggerStatus, PmdSetting | None]]

    @classmethod
    def parse(cls, data: bytes) -> PmdOfflineTrigger:
        if not data:
            raise PmdProtocolError("Offline trigger status response is empty.")
        try:
            mode = PmdOfflineRecTriggerMode(data[0])
        except ValueError as exc:
            raise PmdProtocolError(f"Unknown offline trigger mode: {data[0]}") from exc
        offset = 1
        triggers: dict[
            PmdMeasurementType, tuple[PmdOfflineRecTriggerStatus, PmdSetting | None]
        ] = {}
        while offset < len(data):
            if offset + 2 > len(data):
                raise PmdProtocolError("Broken offline trigger response.")
            try:
                status = PmdOfflineRecTriggerStatus(data[offset])
            except ValueError as exc:
                raise PmdProtocolError(f"Unknown offline trigger status: {data[offset]}") from exc
            offset += 1
            measurement_type = PmdMeasurementType.from_status_byte(data[offset])
            offset += 1
            setting: PmdSetting | None = None
            if status == PmdOfflineRecTriggerStatus.ENABLED:
                if offset >= len(data):
                    raise PmdProtocolError("Offline trigger setting length is missing.")
                setting_length = data[offset]
                offset += 1
                if offset + setting_length > len(data):
                    raise PmdProtocolError("Broken offline trigger settings.")
                setting_bytes = data[offset : offset + setting_length]
                offset += setting_length
                setting = PmdSetting.parse(setting_bytes) if setting_bytes else None
            triggers[measurement_type] = (status, setting)
        return cls(mode=mode, triggers=triggers)

    def to_jsonable(self) -> dict[str, object]:
        rendered: dict[str, object] = {}
        for measurement_type, (status, setting) in self.triggers.items():
            rendered[measurement_type.name] = {
                "status": status.name,
                "settings": setting.to_jsonable() if setting is not None else None,
            }
        return {"mode": self.mode.name, "triggers": rendered}


@dataclass(frozen=True)
class PmdControlPointResponse:
    op_code: PmdControlPointCommand | None
    measurement_type: int
    response_code: PmdResponseCode
    more: bool
    parameters: bytes

    @classmethod
    def parse(cls, data: bytes) -> PmdControlPointResponse:
        if len(data) < 4:
            raise PmdProtocolError("PMD control-point response is too short.")
        if data[0] != CONTROL_POINT_RESPONSE_CODE:
            raise PmdProtocolError("Not a PMD control-point response.")
        try:
            op_code = PmdControlPointCommand(data[1])
        except ValueError:
            op_code = None
        response_code = PmdResponseCode.from_byte(data[3])
        more = response_code == PmdResponseCode.SUCCESS and len(data) > 4 and data[4] != 0
        parameters = data[5:] if response_code == PmdResponseCode.SUCCESS and len(data) > 5 else b""
        return cls(
            op_code=op_code,
            measurement_type=data[2],
            response_code=response_code,
            more=more,
            parameters=parameters,
        )


POLAR_TO_PMD: dict[PolarDeviceDataType, PmdMeasurementType] = {
    PolarDeviceDataType.ECG: PmdMeasurementType.ECG,
    PolarDeviceDataType.ACC: PmdMeasurementType.ACC,
    PolarDeviceDataType.PPG: PmdMeasurementType.PPG,
    PolarDeviceDataType.PPI: PmdMeasurementType.PPI,
    PolarDeviceDataType.GYRO: PmdMeasurementType.GYRO,
    PolarDeviceDataType.MAGNETOMETER: PmdMeasurementType.MAGNETOMETER,
    PolarDeviceDataType.LOCATION: PmdMeasurementType.LOCATION,
    PolarDeviceDataType.PRESSURE: PmdMeasurementType.PRESSURE,
    PolarDeviceDataType.TEMPERATURE: PmdMeasurementType.TEMPERATURE,
    PolarDeviceDataType.SKIN_TEMPERATURE: PmdMeasurementType.SKIN_TEMP,
    PolarDeviceDataType.HR: PmdMeasurementType.OFFLINE_HR,
}
PMD_TO_POLAR: dict[PmdMeasurementType, PolarDeviceDataType] = {
    value: key for key, value in POLAR_TO_PMD.items()
}


def normalize_polar_data_type(
    data_type: PolarDeviceDataType | str,
) -> PolarDeviceDataType:
    if isinstance(data_type, PolarDeviceDataType):
        return data_type
    try:
        return PolarDeviceDataType[data_type.replace("-", "_").upper()]
    except KeyError as exc:
        raise PmdUnsupportedOperation(f"Unsupported Polar data type: {data_type}") from exc


def map_polar_to_pmd(data_type: PolarDeviceDataType | str) -> PmdMeasurementType:
    polar_type = normalize_polar_data_type(data_type)
    return POLAR_TO_PMD[polar_type]


def map_pmd_to_polar(measurement_type: PmdMeasurementType) -> PolarDeviceDataType:
    try:
        return PMD_TO_POLAR[measurement_type]
    except KeyError as exc:
        raise PmdUnsupportedOperation(
            f"PMD measurement type is not a Polar data type: {measurement_type.name}"
        ) from exc


def parse_pmd_features(data: bytes) -> set[PmdMeasurementType]:
    if len(data) < 3:
        raise PmdProtocolError("PMD feature data must contain at least 3 bytes.")
    features: set[PmdMeasurementType] = set()
    if data[1] & 0x01:
        features.add(PmdMeasurementType.ECG)
    if data[1] & 0x02:
        features.add(PmdMeasurementType.PPG)
    if data[1] & 0x04:
        features.add(PmdMeasurementType.ACC)
    if data[1] & 0x08:
        features.add(PmdMeasurementType.PPI)
    if data[1] & 0x20:
        features.add(PmdMeasurementType.GYRO)
    if data[1] & 0x40:
        features.add(PmdMeasurementType.MAGNETOMETER)
    if data[1] & 0x80:
        features.add(PmdMeasurementType.SKIN_TEMP)
    if data[2] & 0x02:
        features.add(PmdMeasurementType.SDK_MODE)
    if data[2] & 0x04:
        features.add(PmdMeasurementType.LOCATION)
    if data[2] & 0x08:
        features.add(PmdMeasurementType.PRESSURE)
    if data[2] & 0x10:
        features.add(PmdMeasurementType.TEMPERATURE)
    if data[2] & 0x20:
        features.add(PmdMeasurementType.OFFLINE_RECORDING)
    if data[2] & 0x40:
        features.add(PmdMeasurementType.OFFLINE_HR)
    return features


def offline_data_types_from_features(
    features: set[PmdMeasurementType],
) -> set[PolarDeviceDataType]:
    if PmdMeasurementType.OFFLINE_RECORDING not in features:
        raise PmdUnsupportedOperation("PMD offline recording feature is not available.")
    data_types: set[PolarDeviceDataType] = set()
    for measurement_type in features:
        try:
            data_types.add(map_pmd_to_polar(measurement_type))
        except PmdUnsupportedOperation:
            continue
    return data_types
