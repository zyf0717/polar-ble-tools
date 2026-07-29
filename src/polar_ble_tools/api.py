"""High-level Python entry points matching operational CLI workflows."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Callable, Mapping

from polar_ble_tools.device import PolarDeviceTarget, resolve_polar_device_target
from polar_ble_tools.polar.offline import (
    OfflineRecordingEntry,
    OfflineRecordingTrigger,
    parse_offline_recording_path,
)
from polar_ble_tools.polar.pftp import PftpProtocolError
from polar_ble_tools.polar.pmd import (
    PmdOfflineRecTriggerMode,
    PmdSetting,
    PmdSettingType,
    PmdUnsupportedOperation,
    PolarDeviceDataType,
    normalize_polar_data_type,
)
from polar_ble_tools.storage_utils import atomic_write_bytes
from polar_ble_tools.workflows import DeviceWorkflowRunner

if TYPE_CHECKING:
    from polar_ble_tools.ble.transport import BleTransport
    from polar_ble_tools.polar.setup import (
        FtuProfile,
        PhysicalConfiguration,
        UserDeviceSettings,
        UserDeviceSettingsPatch,
    )
    from polar_ble_tools.rec import DecoderStatus
    from polar_ble_tools.schemas.cache import SdkCache
    from polar_ble_tools.sdk_tools.downloader import SdkStatus


@dataclass(frozen=True)
class DoctorSchemaStatus:
    ready: bool
    active_commit: str | None = None
    path: Path | None = None
    error: str | None = None
    remediation: str | None = None

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["path"] = str(self.path) if self.path is not None else None
        return result


@dataclass(frozen=True)
class DoctorReport:
    sdk: SdkStatus
    schemas: DoctorSchemaStatus
    decoder: DecoderStatus
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "core": {"ready": True},
            "sdk": {
                "active_commit": self.sdk.active_commit,
                "installed_commits": list(self.sdk.installed_commits),
            },
            "schemas": self.schemas.to_dict(),
            "decoder": asdict(self.decoder),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class FtuApplyResult:
    ftu_applied: bool
    settings_updated: bool


@dataclass(frozen=True)
class RecordingTypesResult:
    device_id: str
    types: tuple[PolarDeviceDataType, ...]

    def to_jsonable(self) -> dict[str, object]:
        return {"device_id": self.device_id, "types": [item.value for item in self.types]}


@dataclass(frozen=True)
class RecordingStatusResult:
    device_id: str
    active_by_type: Mapping[PolarDeviceDataType, bool]
    observed_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "active_by_type", MappingProxyType(dict(self.active_by_type)))

    def to_jsonable(self) -> dict[str, object]:
        return {
            "device_id": self.device_id,
            "active_by_type": {
                item.value: self.active_by_type[item]
                for item in sorted(self.active_by_type, key=lambda value: value.value)
            },
            "observed_at": _timestamp(self.observed_at),
        }


@dataclass(frozen=True)
class RecordingSettingsResult:
    device_id: str
    recording_type: PolarDeviceDataType
    full: bool
    settings: Mapping[str, tuple[int, ...]]

    def __post_init__(self) -> None:
        object.__setattr__(self, "settings", MappingProxyType(dict(self.settings)))

    def to_jsonable(self) -> dict[str, object]:
        return {
            "device_id": self.device_id,
            "recording_type": self.recording_type.value,
            "full": self.full,
            "settings": {key: list(values) for key, values in self.settings.items()},
        }


@dataclass(frozen=True)
class RecordingCommandResult:
    device_id: str
    recording_type: PolarDeviceDataType
    operation: str
    active: bool
    observed_at: datetime

    def to_jsonable(self) -> dict[str, object]:
        return {
            "device_id": self.device_id,
            "recording_type": self.recording_type.value,
            "operation": self.operation,
            "active": self.active,
            "observed_at": _timestamp(self.observed_at),
        }


@dataclass(frozen=True)
class OfflineTriggerResult:
    device_id: str
    mode: str
    trigger_features: Mapping[PolarDeviceDataType, Mapping[str, tuple[int, ...]] | None]
    observed_at: datetime
    updated: bool = False

    def __post_init__(self) -> None:
        features = {
            data_type: None if settings is None else MappingProxyType(dict(settings))
            for data_type, settings in self.trigger_features.items()
        }
        object.__setattr__(self, "trigger_features", MappingProxyType(features))

    def to_jsonable(self) -> dict[str, object]:
        return {
            "device_id": self.device_id,
            "mode": self.mode,
            "trigger_features": {
                data_type.value: None
                if settings is None
                else {key: list(values) for key, values in settings.items()}
                for data_type, settings in sorted(
                    self.trigger_features.items(), key=lambda item: item[0].value
                )
            },
            "observed_at": _timestamp(self.observed_at),
            "updated": self.updated,
        }


@dataclass(frozen=True)
class DeviceDiskSpaceResult:
    device_id: str
    fragment_size: int
    total_fragments: int
    free_fragments: int
    total_bytes: int
    free_bytes: int
    used_bytes: int
    observed_at: datetime

    def to_jsonable(self) -> dict[str, object]:
        return {
            "device_id": self.device_id,
            "fragment_size": self.fragment_size,
            "total_fragments": self.total_fragments,
            "free_fragments": self.free_fragments,
            "total_bytes": self.total_bytes,
            "free_bytes": self.free_bytes,
            "used_bytes": self.used_bytes,
            "observed_at": _timestamp(self.observed_at),
        }


@dataclass(frozen=True)
class RawFetchResult:
    device_id: str
    device_path: str
    output_path: Path
    fetched_size: int
    sha256: str
    observed_at: datetime

    def to_jsonable(self) -> dict[str, object]:
        return {
            "device_id": self.device_id,
            "device_path": self.device_path,
            "output_path": str(self.output_path),
            "fetched_size": self.fetched_size,
            "sha256": self.sha256,
            "observed_at": _timestamp(self.observed_at),
        }


def doctor(*, cache: SdkCache | None = None) -> DoctorReport:
    """Return core, SDK-schema, and REC-decoder readiness without mutation."""
    from polar_ble_tools.rec import decoder_status
    from polar_ble_tools.schemas.cache import SdkCache
    from polar_ble_tools.sdk_tools.downloader import sdk_status
    from polar_ble_tools.sdk_tools.verifier import (
        SchemaVerificationError,
        schema_status,
        verify_active_schemas,
    )

    cache = cache or SdkCache.default()
    sdk = sdk_status(cache=cache)
    schema_state = schema_status(cache=cache)
    if schema_state.active_commit is None:
        schemas = DoctorSchemaStatus(ready=False, remediation="polar-ble sdk install")
    else:
        try:
            schema_root = verify_active_schemas(cache=cache)
        except (SchemaVerificationError, OSError, ValueError) as exc:
            schemas = DoctorSchemaStatus(
                ready=False,
                active_commit=schema_state.active_commit,
                error=str(exc),
                remediation="polar-ble sdk schemas verify",
            )
        else:
            schemas = DoctorSchemaStatus(
                ready=True, active_commit=schema_state.active_commit, path=schema_root
            )
    decoder = decoder_status(cache=cache)
    warnings = ()
    if (
        sdk.active_commit is not None
        and decoder.sdk_commit is not None
        and sdk.active_commit != decoder.sdk_commit
    ):
        warnings = (
            f"Active SDK {sdk.active_commit} differs from active REC decoder SDK "
            f"{decoder.sdk_commit}. The decoder remains usable; rebuild it against "
            "the active SDK if that revision is supported: polar-ble sdk decoder build",
        )
    return DoctorReport(sdk=sdk, schemas=schemas, decoder=decoder, warnings=warnings)


async def apply_ftu(
    target: PolarDeviceTarget | str,
    profile: FtuProfile,
    *,
    transport_factory: Callable[[], BleTransport] | None = None,
) -> FtuApplyResult:
    """Apply a validated FTU profile and its optional initial settings patch."""
    resolved = resolve_polar_device_target(target)

    async def workflow(device):
        setup = device.services.setup
        await setup.do_first_time_use(profile)
        patch = profile.user_device_settings
        if patch is not None and patch.has_changes:
            await setup.set_user_device_settings(patch)
            return FtuApplyResult(ftu_applied=True, settings_updated=True)
        return FtuApplyResult(ftu_applied=True, settings_updated=False)

    return await DeviceWorkflowRunner(transport_factory=transport_factory).run(resolved, workflow)


async def ftu_status(
    target: PolarDeviceTarget | str, *, transport_factory: Callable[[], BleTransport] | None = None
) -> bool:
    resolved = resolve_polar_device_target(target)

    async def workflow(device):
        return await device.services.setup.is_ftu_done()

    return await DeviceWorkflowRunner(transport_factory=transport_factory).run(resolved, workflow)


async def physical_configuration(
    target: PolarDeviceTarget | str, *, transport_factory: Callable[[], BleTransport] | None = None
) -> PhysicalConfiguration | None:
    resolved = resolve_polar_device_target(target)

    async def workflow(device):
        return await device.services.setup.get_physical_configuration()

    return await DeviceWorkflowRunner(transport_factory=transport_factory).run(resolved, workflow)


async def user_device_settings(
    target: PolarDeviceTarget | str, *, transport_factory: Callable[[], BleTransport] | None = None
) -> UserDeviceSettings:
    resolved = resolve_polar_device_target(target)

    async def workflow(device):
        return await device.services.setup.get_user_device_settings()

    return await DeviceWorkflowRunner(transport_factory=transport_factory).run(resolved, workflow)


async def update_user_device_settings(
    target: PolarDeviceTarget | str,
    patch: UserDeviceSettingsPatch,
    *,
    transport_factory: Callable[[], BleTransport] | None = None,
) -> None:
    resolved = resolve_polar_device_target(target)

    async def workflow(device):
        await device.services.setup.set_user_device_settings(patch)

    await DeviceWorkflowRunner(transport_factory=transport_factory).run(resolved, workflow)


async def diagnose_ftu(
    target: PolarDeviceTarget | str, *, transport_factory: Callable[[], BleTransport] | None = None
) -> dict[str, object]:
    resolved = resolve_polar_device_target(target)

    async def workflow(device):
        return await device.services.setup.diagnose_setup()

    return await DeviceWorkflowRunner(transport_factory=transport_factory).run(resolved, workflow)


async def available_recording_types(
    target: PolarDeviceTarget | str,
    *,
    transport_factory: Callable[[], BleTransport] | None = None,
) -> RecordingTypesResult:
    """Return recording types reported by one device."""
    resolved = resolve_polar_device_target(target)

    async def workflow(device):
        return await device.services.offline_control.get_available_recording_types()

    types = await DeviceWorkflowRunner(transport_factory=transport_factory).run(resolved, workflow)
    return RecordingTypesResult(
        device_id=_device_id(resolved), types=tuple(sorted(types, key=lambda item: item.value))
    )


async def recording_status(
    target: PolarDeviceTarget | str,
    *,
    transport_factory: Callable[[], BleTransport] | None = None,
) -> RecordingStatusResult:
    """Return the current offline-active state for each reported recording type."""
    resolved = resolve_polar_device_target(target)

    async def workflow(device):
        return await device.services.offline_control.get_recording_status()

    status = await DeviceWorkflowRunner(transport_factory=transport_factory).run(resolved, workflow)
    return RecordingStatusResult(
        device_id=_device_id(resolved), active_by_type=status, observed_at=datetime.now(UTC)
    )


async def recording_settings(
    target: PolarDeviceTarget | str,
    recording_type: PolarDeviceDataType | str,
    *,
    full: bool = False,
    transport_factory: Callable[[], BleTransport] | None = None,
) -> RecordingSettingsResult:
    """Return current or full offline settings for one recording type."""
    normalized_type = normalize_polar_data_type(recording_type)
    if normalized_type in {PolarDeviceDataType.HR, PolarDeviceDataType.PPI}:
        raise PmdUnsupportedOperation(
            f"{normalized_type.value} offline settings are not supported."
        )
    resolved = resolve_polar_device_target(target)

    async def workflow(device):
        control = device.services.offline_control
        if full:
            return await control.request_full_recording_settings(normalized_type)
        return await control.request_recording_settings(normalized_type)

    setting = await DeviceWorkflowRunner(transport_factory=transport_factory).run(
        resolved, workflow
    )
    return RecordingSettingsResult(
        device_id=_device_id(resolved),
        recording_type=normalized_type,
        full=full,
        settings=_setting_values(setting),
    )


async def start_recording(
    target: PolarDeviceTarget | str,
    recording_type: PolarDeviceDataType | str,
    settings: Mapping[str, int] | None = None,
    *,
    transport_factory: Callable[[], BleTransport] | None = None,
) -> RecordingCommandResult:
    """Start an offline recording after local type and setting validation."""
    normalized_type = normalize_polar_data_type(recording_type)
    selected = _selected_settings(settings)
    resolved = resolve_polar_device_target(target)

    async def workflow(device):
        await device.services.offline_control.start_recording(normalized_type, selected)

    await DeviceWorkflowRunner(transport_factory=transport_factory).run(resolved, workflow)
    return RecordingCommandResult(
        device_id=_device_id(resolved),
        recording_type=normalized_type,
        operation="start",
        active=True,
        observed_at=datetime.now(UTC),
    )


async def stop_recording(
    target: PolarDeviceTarget | str,
    recording_type: PolarDeviceDataType | str,
    *,
    transport_factory: Callable[[], BleTransport] | None = None,
) -> RecordingCommandResult:
    """Stop an offline recording and wait for the bounded inactive transition."""
    normalized_type = normalize_polar_data_type(recording_type)
    resolved = resolve_polar_device_target(target)

    async def workflow(device):
        await device.services.offline_control.stop_recording(normalized_type)

    await DeviceWorkflowRunner(transport_factory=transport_factory).run(resolved, workflow)
    return RecordingCommandResult(
        device_id=_device_id(resolved),
        recording_type=normalized_type,
        operation="stop",
        active=False,
        observed_at=datetime.now(UTC),
    )


async def offline_trigger(
    target: PolarDeviceTarget | str,
    *,
    transport_factory: Callable[[], BleTransport] | None = None,
) -> OfflineTriggerResult:
    """Return the current normalized offline recording trigger configuration."""
    resolved = resolve_polar_device_target(target)

    async def workflow(device):
        return await device.services.offline_control.get_trigger_setup()

    trigger = await DeviceWorkflowRunner(transport_factory=transport_factory).run(
        resolved, workflow
    )
    return _trigger_result(_device_id(resolved), trigger)


async def update_offline_trigger(
    target: PolarDeviceTarget | str,
    mode: str,
    trigger_features: Mapping[PolarDeviceDataType | str, Mapping[str, int] | None],
    *,
    transport_factory: Callable[[], BleTransport] | None = None,
) -> OfflineTriggerResult:
    """Validate and replace the offline recording trigger configuration."""
    normalized_mode = _trigger_mode(mode)
    normalized_features = _trigger_features(trigger_features)
    if normalized_mode == PmdOfflineRecTriggerMode.DISABLED and normalized_features:
        raise ValueError("Disabled trigger mode requires no recording types.")
    if normalized_mode != PmdOfflineRecTriggerMode.DISABLED and not normalized_features:
        raise ValueError("A non-disabled trigger mode requires at least one recording type.")
    if (
        normalized_mode == PmdOfflineRecTriggerMode.EXERCISE_START
        and PolarDeviceDataType.PPI in normalized_features
    ):
        raise ValueError("PPI exercise-start offline trigger is not supported.")
    trigger = OfflineRecordingTrigger(mode=normalized_mode, trigger_features=normalized_features)
    resolved = resolve_polar_device_target(target)

    async def workflow(device):
        await device.services.offline_control.set_trigger_setup(trigger)

    await DeviceWorkflowRunner(transport_factory=transport_factory).run(resolved, workflow)
    return _trigger_result(_device_id(resolved), trigger, updated=True)


async def device_disk_space(
    target: PolarDeviceTarget | str,
    *,
    transport_factory: Callable[[], BleTransport] | None = None,
) -> DeviceDiskSpaceResult:
    """Return validated device PFTP disk-space counters and derived byte totals."""
    resolved = resolve_polar_device_target(target)

    async def workflow(device):
        return await device.services.pftp.get_disk_space()

    disk_space = await DeviceWorkflowRunner(transport_factory=transport_factory).run(
        resolved, workflow
    )
    values = (disk_space.fragment_size, disk_space.total_fragments, disk_space.free_fragments)
    if any(value < 0 for value in values) or disk_space.free_fragments > disk_space.total_fragments:
        raise PftpProtocolError("Invalid PFTP disk-space counters.")
    return DeviceDiskSpaceResult(
        device_id=_device_id(resolved),
        fragment_size=disk_space.fragment_size,
        total_fragments=disk_space.total_fragments,
        free_fragments=disk_space.free_fragments,
        total_bytes=disk_space.total_bytes,
        free_bytes=disk_space.free_bytes,
        used_bytes=disk_space.used_bytes,
        observed_at=datetime.now(UTC),
    )


async def fetch_raw_recording(
    target: PolarDeviceTarget | str,
    device_path: str,
    output_path: str | Path,
    *,
    transport_factory: Callable[[], BleTransport] | None = None,
) -> RawFetchResult:
    """Fetch one validated device REC path and atomically publish it locally."""
    entry: OfflineRecordingEntry = parse_offline_recording_path(device_path, size=0)
    output = _fetch_output_path(output_path, entry.path)
    resolved = resolve_polar_device_target(target)

    async def workflow(device):
        return await device.services.offline.fetch_record(entry)

    record = await DeviceWorkflowRunner(transport_factory=transport_factory).run(resolved, workflow)
    digest = hashlib.sha256(record.payload).hexdigest()
    atomic_write_bytes(output, record.payload)
    return RawFetchResult(
        device_id=_device_id(resolved),
        device_path=entry.path,
        output_path=output,
        fetched_size=len(record.payload),
        sha256=digest,
        observed_at=datetime.now(UTC),
    )


def _device_id(target: PolarDeviceTarget) -> str:
    if target.device_id is None:  # pragma: no cover - resolve invariant
        raise ValueError("Resolved device target is missing device_id.")
    return target.device_id


def _setting_values(setting: PmdSetting) -> Mapping[str, tuple[int, ...]]:
    return {
        setting_type.name: tuple(sorted(values))
        for setting_type, values in sorted(setting.settings.items(), key=lambda item: item[0].name)
    }


def _selected_settings(settings: Mapping[str, int] | None) -> PmdSetting:
    if settings is None:
        return PmdSetting()
    selected: dict[PmdSettingType, int] = {}
    for raw_key, raw_value in settings.items():
        if not isinstance(raw_key, str):
            raise ValueError("Recording setting keys must be strings.")
        normalized_key = raw_key.strip().replace("-", "_").upper()
        if not normalized_key:
            raise ValueError("Recording setting key is empty.")
        setting_type = PmdSettingType.from_name(normalized_key)
        if setting_type in selected:
            raise ValueError(f"Duplicate recording setting: {normalized_key}")
        if not isinstance(raw_value, int) or isinstance(raw_value, bool):
            raise ValueError(f"Recording setting {normalized_key} must be an integer.")
        selected[setting_type] = raw_value
    result = PmdSetting.from_selected(selected)
    result.serialize_selected()
    return result


def _trigger_mode(raw_mode: str) -> PmdOfflineRecTriggerMode:
    normalized = raw_mode.strip().replace("_", "-").lower()
    modes = {
        "disabled": PmdOfflineRecTriggerMode.DISABLED,
        "system-start": PmdOfflineRecTriggerMode.SYSTEM_START,
        "exercise-start": PmdOfflineRecTriggerMode.EXERCISE_START,
    }
    try:
        return modes[normalized]
    except KeyError as exc:
        raise ValueError(f"Unsupported offline trigger mode: {raw_mode}") from exc


def _trigger_features(
    features: Mapping[PolarDeviceDataType | str, Mapping[str, int] | None],
) -> dict[PolarDeviceDataType, PmdSetting | None]:
    normalized: dict[PolarDeviceDataType, PmdSetting | None] = {}
    for raw_type, settings in features.items():
        recording_type = normalize_polar_data_type(raw_type)
        if recording_type in normalized:
            raise ValueError(f"Duplicate trigger recording type: {recording_type.value}")
        normalized[recording_type] = None if settings is None else _selected_settings(settings)
    return normalized


def _trigger_result(
    device_id: str, trigger: OfflineRecordingTrigger, *, updated: bool = False
) -> OfflineTriggerResult:
    return OfflineTriggerResult(
        device_id=device_id,
        mode={
            PmdOfflineRecTriggerMode.DISABLED: "disabled",
            PmdOfflineRecTriggerMode.SYSTEM_START: "system-start",
            PmdOfflineRecTriggerMode.EXERCISE_START: "exercise-start",
        }[trigger.mode],
        trigger_features={
            recording_type: None if setting is None else _setting_values(setting)
            for recording_type, setting in trigger.trigger_features.items()
        },
        observed_at=datetime.now(UTC),
        updated=updated,
    )


def _fetch_output_path(output_path: str | Path, device_path: str) -> Path:
    output = Path(output_path).expanduser()
    if str(output) == device_path:
        raise ValueError("Raw fetch output must not alias the device source path.")
    if output.is_symlink():
        raise ValueError("Raw fetch output must not be a symlink.")
    if output.exists():
        raise FileExistsError(f"Raw fetch output already exists: {output}")
    return output.resolve(strict=False)


def _timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
