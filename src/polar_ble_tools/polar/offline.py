from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePosixPath

from polar_ble_tools.ble.lifecycle import BleLifecycle, BleLifecycleEvent
from polar_ble_tools.ble.transport import BleConnectionError, BleTransportError
from polar_ble_tools.polar._protobuf import PftpDirectoryEntry
from polar_ble_tools.polar.pftp import PftpClient, PftpResponseError
from polar_ble_tools.polar.pmd import (
    PmdActiveMeasurement,
    PmdClient,
    PmdMeasurementType,
    PmdOfflineRecTriggerMode,
    PmdOfflineRecTriggerStatus,
    PmdOfflineTrigger,
    PmdSecret,
    PmdSetting,
    PmdUnsupportedOperation,
    PolarDeviceDataType,
    map_pmd_to_polar,
    map_polar_to_pmd,
    normalize_polar_data_type,
)

NO_SUCH_FILE_OR_DIRECTORY = 103
OFFLINE_RECORDING_RE = re.compile(
    r"^/U/(?P<user>\d+)/(?P<date>\d{8})/R/(?P<time>\d{6})/(?P<filename>[^/]+\.REC)$",
    re.IGNORECASE,
)
USER_DIRECTORY_RE = re.compile(r"^\d+/?$")
DAY_DIRECTORY_RE = re.compile(r"^\d{8}/?$")
TIME_DIRECTORY_RE = re.compile(r"^\d{6}/?$")
NUMBERED_RECORD_TYPE_RE = re.compile(r"^(?P<base>.*?)(?P<part>\d+)$")
RECORD_TYPE_ALIASES = {
    "MAG": "MAGNETOMETER",
    "SKINTEMP": "SKIN_TEMPERATURE",
    "SKIN_TEMP": "SKIN_TEMPERATURE",
    "TEMP": "TEMPERATURE",
}


@dataclass(frozen=True)
class OfflineRecordingEntry:
    path: str
    size: int
    record_type: str
    user_index: int
    started_at: datetime | None = None


@dataclass(frozen=True)
class OfflineRecord:
    entry: OfflineRecordingEntry
    payload: bytes


@dataclass(frozen=True)
class DeviceDeletionResult:
    device_path: str
    record_type: str
    base_record_type: str | None
    status: str
    deleted_paths: list[str]
    cleaned_directories: list[str]
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.status in {"deleted", "dry_run"}

    def to_jsonable(self) -> dict[str, object]:
        return {
            "base_record_type": self.base_record_type,
            "cleaned_directories": self.cleaned_directories,
            "deleted_paths": self.deleted_paths,
            "device_path": self.device_path,
            "error": self.error,
            "record_type": self.record_type,
            "status": self.status,
        }


@dataclass(frozen=True)
class OfflineRecordingTrigger:
    mode: PmdOfflineRecTriggerMode
    trigger_features: dict[PolarDeviceDataType, PmdSetting | None]


def split_numbered_record_type(record_type: str) -> tuple[str, int | None]:
    normalized = record_type.upper()
    match = NUMBERED_RECORD_TYPE_RE.fullmatch(normalized)
    if match is None or not match.group("base"):
        return normalized, None
    return match.group("base"), int(match.group("part"))


def base_record_type_for(record_type: str) -> str | None:
    base, _part_index = split_numbered_record_type(record_type)
    aliased = RECORD_TYPE_ALIASES.get(base, base)
    try:
        return PolarDeviceDataType[aliased].value
    except KeyError:
        return None


def record_type_family_key(record_type: str) -> str:
    base, _part_index = split_numbered_record_type(record_type)
    return base_record_type_for(base) or RECORD_TYPE_ALIASES.get(base, base)


def record_type_matches_filter(record_type: str, requested_type: str) -> bool:
    normalized = record_type.upper()
    requested = requested_type.replace("-", "_").upper()
    return normalized == requested or record_type_family_key(normalized) == (
        base_record_type_for(requested) or record_type_family_key(requested)
    )


def record_type_matches_deletion_family(
    target_record_type: str,
    candidate_record_type: str,
) -> bool:
    target_base, target_part = split_numbered_record_type(target_record_type)
    candidate_base, candidate_part = split_numbered_record_type(candidate_record_type)
    if record_type_family_key(target_base) != record_type_family_key(candidate_base):
        return False
    return target_part is None or candidate_part is not None


def parse_offline_recording_path(path: str, *, size: int) -> OfflineRecordingEntry:
    match = OFFLINE_RECORDING_RE.fullmatch(path)
    if match is None:
        raise ValueError(f"Not a Polar offline recording path: {path}")
    try:
        started_at = datetime.strptime(match.group("date") + match.group("time"), "%Y%m%d%H%M%S")
    except ValueError:
        started_at = None
    return OfflineRecordingEntry(
        path=path,
        size=size,
        record_type=PurePosixPath(match.group("filename")).stem.upper(),
        user_index=int(match.group("user")),
        started_at=started_at,
    )


class OfflineRecordingClient:
    def __init__(
        self,
        pftp_client: PftpClient,
        *,
        lifecycle: BleLifecycle | None = None,
    ) -> None:
        self.pftp_client = pftp_client
        self.lifecycle = lifecycle

    async def list_recording_files(self) -> list[OfflineRecordingEntry]:
        self._transition(BleLifecycleEvent.START_TRANSFER, "list recordings")
        try:
            entries = await self._walk_recordings()
        except Exception as exc:
            self._operation_failed(exc, "list recordings")
            raise
        self._transition(BleLifecycleEvent.TRANSFER_COMPLETE, "list recordings")
        return entries

    async def fetch_record(self, entry: OfflineRecordingEntry) -> OfflineRecord:
        self._transition(BleLifecycleEvent.START_TRANSFER, entry.path)
        try:
            payload = await self.pftp_client.get_file(entry.path)
        except Exception as exc:
            self._operation_failed(exc, entry.path)
            raise
        self._transition(BleLifecycleEvent.TRANSFER_COMPLETE, entry.path)
        return OfflineRecord(entry=entry, payload=payload)

    async def list_record_family(self, entry: OfflineRecordingEntry) -> list[OfflineRecordingEntry]:
        parent = self._parent_directory(entry.path)
        try:
            candidates = await self.pftp_client.list_directory(parent)
        except PftpResponseError as exc:
            if exc.error_code == NO_SUCH_FILE_OR_DIRECTORY:
                return [entry]
            raise
        family: list[OfflineRecordingEntry] = []
        for candidate in candidates:
            if not candidate.name.upper().endswith(".REC"):
                continue
            try:
                candidate_entry = parse_offline_recording_path(
                    self._join_file(parent, candidate.name), size=candidate.size
                )
            except ValueError:
                continue
            if record_type_matches_deletion_family(entry.record_type, candidate_entry.record_type):
                family.append(candidate_entry)
        return sorted(family or [entry], key=lambda item: item.path)

    async def remove_record(
        self, entry: OfflineRecordingEntry, *, dry_run: bool = False
    ) -> DeviceDeletionResult:
        self._transition(BleLifecycleEvent.START_TRANSFER, f"remove {entry.path}")
        deleted_paths: list[str] = []
        cleaned_directories: list[str] = []
        try:
            family = await self.list_record_family(entry)
            deleted_paths = [record.path for record in family]
            if dry_run:
                self._transition(BleLifecycleEvent.TRANSFER_COMPLETE, f"remove {entry.path}")
                return DeviceDeletionResult(
                    device_path=entry.path,
                    record_type=entry.record_type,
                    base_record_type=base_record_type_for(entry.record_type),
                    status="dry_run",
                    deleted_paths=deleted_paths,
                    cleaned_directories=[],
                )
            for path in deleted_paths:
                await self.pftp_client.remove_file(path)
            cleaned_directories = await self._remove_empty_parent_directories(entry.path)
        except Exception as exc:
            self._operation_failed(exc, f"remove {entry.path}")
            if isinstance(exc, BleTransportError):
                raise
            return DeviceDeletionResult(
                device_path=entry.path,
                record_type=entry.record_type,
                base_record_type=base_record_type_for(entry.record_type),
                status="failed",
                deleted_paths=deleted_paths,
                cleaned_directories=cleaned_directories,
                error=str(exc),
            )
        self._transition(BleLifecycleEvent.TRANSFER_COMPLETE, f"remove {entry.path}")
        return DeviceDeletionResult(
            device_path=entry.path,
            record_type=entry.record_type,
            base_record_type=base_record_type_for(entry.record_type),
            status="deleted",
            deleted_paths=deleted_paths,
            cleaned_directories=cleaned_directories,
        )

    async def _walk_recordings(self) -> list[OfflineRecordingEntry]:
        recordings: list[OfflineRecordingEntry] = []
        for user in await self._list_or_empty("/U/"):
            if USER_DIRECTORY_RE.fullmatch(user.name) is None:
                continue
            user_path = self._join_directory("/U/", user.name)
            for day in await self._list_or_empty(user_path):
                if DAY_DIRECTORY_RE.fullmatch(day.name) is None:
                    continue
                day_path = self._join_directory(user_path, day.name)
                record_root = await self._recording_root_or_none(day_path)
                if record_root is None:
                    continue
                for start_time in await self._list_or_empty(record_root):
                    if TIME_DIRECTORY_RE.fullmatch(start_time.name) is None:
                        continue
                    time_path = self._join_directory(record_root, start_time.name)
                    for candidate in await self._list_or_empty(time_path):
                        if not candidate.name.upper().endswith(".REC"):
                            continue
                        try:
                            recordings.append(
                                parse_offline_recording_path(
                                    self._join_file(time_path, candidate.name),
                                    size=candidate.size,
                                )
                            )
                        except ValueError:
                            continue
        return recordings

    async def _recording_root_or_none(self, day_path: str) -> str | None:
        for child in await self._list_or_empty(day_path):
            if child.name.strip("/").upper() == "R":
                return self._join_directory(day_path, child.name)
        return None

    async def _list_or_empty(self, path: str) -> list[PftpDirectoryEntry]:
        try:
            return await self.pftp_client.list_directory(path)
        except PftpResponseError as exc:
            if exc.error_code == NO_SUCH_FILE_OR_DIRECTORY:
                return []
            raise

    async def _remove_empty_parent_directories(self, entry_path: str) -> list[str]:
        cleaned: list[str] = []
        for directory in self._cleanup_parent_directories(entry_path):
            try:
                entries = await self.pftp_client.list_directory(directory)
            except PftpResponseError as exc:
                if exc.error_code == NO_SUCH_FILE_OR_DIRECTORY:
                    continue
                raise
            if entries:
                break
            await self.pftp_client.remove_file(directory)
            cleaned.append(directory)
        return cleaned

    def _transition(self, event: BleLifecycleEvent, detail: str) -> None:
        if self.lifecycle is not None:
            self.lifecycle.transition(event, detail=detail)

    def _operation_failed(self, exc: Exception, detail: str) -> None:
        if self.lifecycle is None:
            return
        # A per-record protocol failure does not imply the BLE link is dead;
        # restore SERVICES_READY so later independent records can continue.
        if isinstance(exc, (BleConnectionError, BleTransportError)):
            self.lifecycle.fail(str(exc))
        else:
            self.lifecycle.transition(
                BleLifecycleEvent.TRANSFER_COMPLETE, detail=f"failed: {detail}"
            )

    @staticmethod
    def _join_directory(base: str, name: str) -> str:
        return f"{base.rstrip('/')}/{name.strip('/')}/"

    @staticmethod
    def _join_file(base: str, name: str) -> str:
        return f"{base.rstrip('/')}/{name.strip('/')}"

    @staticmethod
    def _parent_directory(path: str) -> str:
        return f"{path.rsplit('/', 1)[0]}/"

    @staticmethod
    def _cleanup_parent_directories(path: str) -> list[str]:
        match = OFFLINE_RECORDING_RE.fullmatch(path)
        if match is None:
            return []
        user_root = f"/U/{match.group('user')}/"
        current = OfflineRecordingClient._parent_directory(path)
        directories: list[str] = []
        while current != user_root:
            directories.append(current)
            current = OfflineRecordingClient._parent_directory(current.rstrip("/"))
        return directories


class OfflineRecordingControlClient:
    def __init__(self, pmd_client: PmdClient) -> None:
        self.pmd_client = pmd_client

    async def get_available_recording_types(self) -> set[PolarDeviceDataType]:
        return await self.pmd_client.get_available_offline_data_types()

    async def request_recording_settings(self, data_type: PolarDeviceDataType | str) -> PmdSetting:
        return await self.pmd_client.query_settings(self._settings_measurement_type(data_type))

    async def request_full_recording_settings(
        self, data_type: PolarDeviceDataType | str
    ) -> PmdSetting:
        return await self.pmd_client.query_full_settings(self._settings_measurement_type(data_type))

    async def get_recording_status(self) -> dict[PolarDeviceDataType, bool]:
        pmd_status = await self.pmd_client.read_measurement_status()
        status: dict[PolarDeviceDataType, bool] = {}
        for measurement_type, active_status in pmd_status.items():
            if measurement_type == PmdMeasurementType.DERIVED_MEASUREMENT:
                continue
            try:
                data_type = map_pmd_to_polar(measurement_type)
            except PmdUnsupportedOperation:
                continue
            status[data_type] = active_status in {
                PmdActiveMeasurement.OFFLINE_MEASUREMENT_ACTIVE,
                PmdActiveMeasurement.ONLINE_AND_OFFLINE_ACTIVE,
            }
        return status

    async def start_recording(
        self,
        data_type: PolarDeviceDataType | str,
        settings: PmdSetting | None = None,
        *,
        secret: PmdSecret | None = None,
    ) -> None:
        await self.pmd_client.start_measurement(
            map_polar_to_pmd(data_type), settings, secret=secret
        )

    async def stop_recording(self, data_type: PolarDeviceDataType | str) -> None:
        measurement_type = map_polar_to_pmd(data_type)
        await self.pmd_client.stop_measurement(measurement_type)
        await self.pmd_client.wait_for_measurement_inactive(measurement_type)

    async def get_trigger_setup(self) -> OfflineRecordingTrigger:
        trigger = await self.pmd_client.get_offline_recording_trigger_status()
        return self._map_pmd_trigger_to_offline_trigger(trigger)

    async def set_trigger_setup(
        self, trigger: OfflineRecordingTrigger, *, secret: PmdSecret | None = None
    ) -> None:
        if (
            trigger.mode == PmdOfflineRecTriggerMode.EXERCISE_START
            and PolarDeviceDataType.PPI in trigger.trigger_features
        ):
            raise PmdUnsupportedOperation("PPI exercise-start offline trigger is not supported.")
        pmd_triggers: dict[
            PmdMeasurementType, tuple[PmdOfflineRecTriggerStatus, PmdSetting | None]
        ] = {
            map_polar_to_pmd(data_type): (PmdOfflineRecTriggerStatus.ENABLED, settings)
            for data_type, settings in trigger.trigger_features.items()
        }
        await self.pmd_client.set_offline_recording_trigger(
            PmdOfflineTrigger(mode=trigger.mode, triggers=pmd_triggers), secret=secret
        )

    @staticmethod
    def _settings_measurement_type(
        data_type: PolarDeviceDataType | str,
    ) -> PmdMeasurementType:
        normalized = normalize_polar_data_type(data_type)
        if normalized in {PolarDeviceDataType.HR, PolarDeviceDataType.PPI}:
            raise PmdUnsupportedOperation(f"{normalized.value} offline settings are not supported.")
        return map_polar_to_pmd(normalized)

    @staticmethod
    def _map_pmd_trigger_to_offline_trigger(
        trigger: PmdOfflineTrigger,
    ) -> OfflineRecordingTrigger:
        trigger_features: dict[PolarDeviceDataType, PmdSetting | None] = {}
        for measurement_type, (status, settings) in trigger.triggers.items():
            if status != PmdOfflineRecTriggerStatus.ENABLED:
                continue
            try:
                data_type = map_pmd_to_polar(measurement_type)
            except PmdUnsupportedOperation:
                continue
            trigger_features[data_type] = settings
        return OfflineRecordingTrigger(
            mode=trigger.mode,
            trigger_features=trigger_features,
        )
