from __future__ import annotations

import asyncio
from typing import ClassVar

from polar_ble_tools.ble.transport import BleServiceNotFound, BleSession, LifecyclePhase
from polar_ble_tools.polar import uuids
from polar_ble_tools.polar.pmd_types import (
    CONTROL_POINT_RESPONSE_CODE,
    DEFAULT_STOP_POLL_INTERVAL_SECONDS,
    DEFAULT_STOP_TIMEOUT_SECONDS,
    DEFAULT_TIMEOUT_SECONDS,
    PmdActiveMeasurement,
    PmdControlPointCommand,
    PmdControlPointResponse,
    PmdError,
    PmdMeasurementType,
    PmdOfflineRecTriggerMode,
    PmdOfflineRecTriggerStatus,
    PmdOfflineTrigger,
    PmdProtocolError,
    PmdRecordingType,
    PmdResponseCode,
    PmdResponseError,
    PmdSecret,
    PmdSecurityStrategy,
    PmdSetting,
    PmdSettingType,
    PmdTimeoutError,
    PmdUnsupportedOperation,
    PolarDeviceDataType,
    map_pmd_to_polar,
    map_polar_to_pmd,
    normalize_polar_data_type,
    offline_data_types_from_features,
    parse_pmd_features,
)

__all__ = [
    "PmdActiveMeasurement",
    "PmdClient",
    "PmdControlPointCommand",
    "PmdControlPointResponse",
    "PmdError",
    "PmdMeasurementType",
    "PmdOfflineRecTriggerMode",
    "PmdOfflineRecTriggerStatus",
    "PmdOfflineTrigger",
    "PmdProtocolError",
    "PmdRecordingType",
    "PmdResponseCode",
    "PmdResponseError",
    "PmdSecret",
    "PmdSecurityStrategy",
    "PmdSetting",
    "PmdSettingType",
    "PmdTimeoutError",
    "PmdUnsupportedOperation",
    "PolarDeviceDataType",
    "map_pmd_to_polar",
    "map_polar_to_pmd",
    "normalize_polar_data_type",
    "parse_pmd_features",
]


class PmdClient:
    RESPONSE_CODE: ClassVar[int] = CONTROL_POINT_RESPONSE_CODE

    def __init__(
        self,
        session: BleSession,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.session = session
        self.timeout_seconds = timeout_seconds
        self._control_point_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._request_lock = asyncio.Lock()
        self._response_may_be_stale = False
        self._feature_data: bytes | None = None
        self._notifications_started = False
        self._current_settings: dict[PmdMeasurementType, PmdSetting] = {}

    def ensure_pmd_service(self) -> None:
        normalized = {service.lower() for service in self.session.services}
        if normalized and uuids.PMD_SERVICE not in normalized:
            raise BleServiceNotFound(
                LifecyclePhase.SERVICE_READINESS,
                "Polar PMD service was not discovered.",
            )

    async def start_notifications(self) -> None:
        if self._notifications_started:
            return
        self.ensure_pmd_service()
        await self.session.start_notify(uuids.PMD_CONTROL_POINT, self._on_control_point)
        await self.session.start_notify(uuids.PMD_DATA, self._on_data)
        self._notifications_started = True

    async def stop_notifications(self) -> None:
        if not self._notifications_started:
            return
        await self.session.stop_notify(uuids.PMD_CONTROL_POINT)
        await self.session.stop_notify(uuids.PMD_DATA)
        self._notifications_started = False

    def _on_control_point(self, _sender: str, data: bytes) -> None:
        if data and data[0] == CONTROL_POINT_RESPONSE_CODE:
            self._control_point_queue.put_nowait(data)
            return
        self._feature_data = data

    def _on_data(self, _sender: str, _data: bytes) -> None:
        return

    async def read_features(self) -> set[PmdMeasurementType]:
        await self.start_notifications()
        if self._feature_data is None:
            data = await self.session.read(uuids.PMD_CONTROL_POINT)
            if data and data[0] == CONTROL_POINT_RESPONSE_CODE:
                raise PmdProtocolError("PMD feature read returned a response frame.")
            self._feature_data = data
        return parse_pmd_features(self._feature_data)

    async def get_available_offline_data_types(self) -> set[PolarDeviceDataType]:
        return offline_data_types_from_features(await self.read_features())

    async def query_settings(
        self,
        measurement_type: PmdMeasurementType,
        *,
        recording_type: PmdRecordingType = PmdRecordingType.OFFLINE,
    ) -> PmdSetting:
        request_byte = recording_type.bitfield | int(measurement_type)
        response = await self._request(
            bytes((int(PmdControlPointCommand.GET_MEASUREMENT_SETTINGS), request_byte))
        )
        return PmdSetting.parse(response.parameters)

    async def query_full_settings(
        self,
        measurement_type: PmdMeasurementType,
        *,
        recording_type: PmdRecordingType = PmdRecordingType.OFFLINE,
    ) -> PmdSetting:
        request_byte = recording_type.bitfield | int(measurement_type)
        response = await self._request(
            bytes(
                (
                    int(PmdControlPointCommand.GET_SDK_MODE_MEASUREMENT_SETTINGS),
                    request_byte,
                )
            )
        )
        return PmdSetting.parse(response.parameters)

    async def read_measurement_status(
        self,
    ) -> dict[PmdMeasurementType, PmdActiveMeasurement]:
        response = await self._request(bytes((int(PmdControlPointCommand.GET_MEASUREMENT_STATUS),)))
        status: dict[PmdMeasurementType, PmdActiveMeasurement] = {}
        for value in response.parameters:
            measurement_type = PmdMeasurementType.from_status_byte(value)
            if measurement_type != PmdMeasurementType.UNKNOWN_TYPE:
                status[measurement_type] = PmdActiveMeasurement.from_status_byte(value)
        return status

    async def start_measurement(
        self,
        measurement_type: PmdMeasurementType,
        setting: PmdSetting | None = None,
        *,
        recording_type: PmdRecordingType = PmdRecordingType.OFFLINE,
        secret: PmdSecret | None = None,
    ) -> None:
        setting = setting or PmdSetting()
        request_byte = recording_type.bitfield | int(measurement_type)
        payload = bytearray((int(PmdControlPointCommand.REQUEST_MEASUREMENT_START), request_byte))
        payload.extend(setting.serialize_selected())
        if secret is not None:
            payload.extend(secret.serialize())
        self._current_settings[measurement_type] = setting
        response = await self._request(bytes(payload))
        if response.parameters:
            setting.update_selected_from_start_response(response.parameters)

    async def stop_measurement(self, measurement_type: PmdMeasurementType) -> None:
        await self._request(
            bytes((int(PmdControlPointCommand.STOP_MEASUREMENT), int(measurement_type)))
        )

    async def wait_for_measurement_inactive(
        self,
        measurement_type: PmdMeasurementType,
        *,
        poll_interval_seconds: float = DEFAULT_STOP_POLL_INTERVAL_SECONDS,
        timeout_seconds: float = DEFAULT_STOP_TIMEOUT_SECONDS,
    ) -> None:
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        while True:
            status = await self.read_measurement_status()
            active = status.get(
                measurement_type,
                PmdActiveMeasurement.NO_ACTIVE_MEASUREMENT,
            )
            if active == PmdActiveMeasurement.NO_ACTIVE_MEASUREMENT:
                return
            if asyncio.get_running_loop().time() >= deadline:
                raise PmdTimeoutError(
                    f"Timed out waiting for {measurement_type.name} to become inactive."
                )
            await asyncio.sleep(poll_interval_seconds)

    async def get_offline_recording_trigger_status(self) -> PmdOfflineTrigger:
        response = await self._request(
            bytes((int(PmdControlPointCommand.GET_OFFLINE_RECORDING_TRIGGER_STATUS),))
        )
        return PmdOfflineTrigger.parse(response.parameters)

    async def set_offline_recording_trigger_mode(
        self,
        mode: PmdOfflineRecTriggerMode,
    ) -> None:
        await self._request(
            bytes(
                (
                    int(PmdControlPointCommand.SET_OFFLINE_RECORDING_TRIGGER_MODE),
                    int(mode),
                )
            )
        )

    async def set_offline_recording_trigger_setting(
        self,
        status: PmdOfflineRecTriggerStatus,
        measurement_type: PmdMeasurementType,
        setting: PmdSetting | None = None,
        *,
        secret: PmdSecret | None = None,
    ) -> None:
        if not measurement_type.is_data_type:
            raise PmdProtocolError(f"Invalid PMD data type: {measurement_type.name}")
        payload = bytearray(
            (
                int(PmdControlPointCommand.SET_OFFLINE_RECORDING_TRIGGER_SETTINGS),
                int(status),
                int(measurement_type),
            )
        )
        if status == PmdOfflineRecTriggerStatus.ENABLED:
            settings_bytes = bytearray((setting or PmdSetting()).serialize_selected())
            if secret is not None:
                settings_bytes.extend(secret.serialize())
            if len(settings_bytes) > 0xFF:
                raise PmdProtocolError("Offline trigger settings exceed 255 bytes.")
            payload.append(len(settings_bytes))
            payload.extend(settings_bytes)
        await self._request(bytes(payload))

    async def set_offline_recording_trigger(
        self,
        trigger: PmdOfflineTrigger,
        *,
        secret: PmdSecret | None = None,
    ) -> None:
        await self.set_offline_recording_trigger_mode(trigger.mode)
        if trigger.mode == PmdOfflineRecTriggerMode.DISABLED:
            return
        current = await self.get_offline_recording_trigger_status()
        for measurement_type in current.triggers:
            if measurement_type in trigger.triggers:
                _, setting = trigger.triggers[measurement_type]
                await self.set_offline_recording_trigger_setting(
                    PmdOfflineRecTriggerStatus.ENABLED,
                    measurement_type,
                    setting,
                    secret=secret,
                )
            else:
                await self.set_offline_recording_trigger_setting(
                    PmdOfflineRecTriggerStatus.DISABLED,
                    measurement_type,
                )

    async def _request(self, packet: bytes) -> PmdControlPointResponse:
        if not packet:
            raise PmdProtocolError("PMD command packet is empty.")
        async with self._request_lock:
            await self.start_notifications()
            self._discard_stale_responses()
            await self.session.write(uuids.PMD_CONTROL_POINT, packet, response=True)
            try:
                response = await self._read_response()
            except BaseException:
                self._response_may_be_stale = True
                raise
            if response.response_code != PmdResponseCode.SUCCESS:
                raise PmdResponseError(
                    "PMD control-point request failed",
                    command=response.op_code,
                    response_code=response.response_code,
                    measurement_type=response.measurement_type,
                )
            return response

    def _discard_stale_responses(self) -> None:
        if not self._response_may_be_stale:
            return
        self._response_may_be_stale = False
        while True:
            try:
                self._control_point_queue.get_nowait()
            except asyncio.QueueEmpty:
                return

    async def _read_response(self) -> PmdControlPointResponse:
        chunks = bytearray()
        first_response: PmdControlPointResponse | None = None
        while True:
            try:
                packet = await asyncio.wait_for(
                    self._control_point_queue.get(),
                    timeout=self.timeout_seconds,
                )
            except TimeoutError as exc:
                raise PmdTimeoutError("Timed out waiting for PMD control-point response.") from exc
            response = PmdControlPointResponse.parse(packet)
            if first_response is None:
                first_response = response
            chunks.extend(response.parameters)
            if not response.more:
                return PmdControlPointResponse(
                    op_code=first_response.op_code,
                    measurement_type=first_response.measurement_type,
                    response_code=first_response.response_code,
                    more=False,
                    parameters=bytes(chunks),
                )
