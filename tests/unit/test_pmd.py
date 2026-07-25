import asyncio

from polar_ble_tools.polar import uuids
from polar_ble_tools.polar.pmd import (
    PmdActiveMeasurement,
    PmdClient,
    PmdControlPointCommand,
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
    parse_pmd_features,
)


def cp_response(
    command: PmdControlPointCommand,
    request_byte: int = 0,
    status: PmdResponseCode = PmdResponseCode.SUCCESS,
    parameters: bytes = b"",
    *,
    more: bool = False,
) -> bytes:
    return (
        bytes(
            (
                0xF0,
                int(command),
                request_byte,
                int(status) if status != PmdResponseCode.UNKNOWN_ERROR else 0xFF,
                1 if more else 0,
            )
        )
        + parameters
    )


class FakePmdSession:
    is_connected = True
    services = [uuids.PMD_SERVICE]

    def __init__(self, *, feature_data: bytes = b"\x00\x00\x00") -> None:
        self.feature_data = feature_data
        self.notify_callbacks = {}
        self.responses: dict[bytes, list[bytes]] = {}
        self.writes: list[tuple[str, bytes, bool]] = []

    async def disconnect(self) -> None:
        self.is_connected = False

    async def read(self, characteristic_uuid: str) -> bytes:
        assert characteristic_uuid == uuids.PMD_CONTROL_POINT
        return self.feature_data

    async def write(
        self,
        characteristic_uuid: str,
        data: bytes,
        *,
        response: bool = False,
    ) -> None:
        self.writes.append((characteristic_uuid, data, response))
        callback = self.notify_callbacks[uuids.PMD_CONTROL_POINT]
        for packet in self.responses.get(data, []):
            callback(uuids.PMD_CONTROL_POINT, packet)

    async def start_notify(self, characteristic_uuid: str, callback) -> None:
        self.notify_callbacks[characteristic_uuid] = callback

    async def stop_notify(self, characteristic_uuid: str) -> None:
        self.notify_callbacks.pop(characteristic_uuid, None)


def test_pmd_secret_decrypts_xor_payload() -> None:
    secret = PmdSecret(PmdSecurityStrategy.XOR, b"\x55")

    assert secret.decrypt(b"\x00\x55\xaa") == b"\x55\x00\xff"


def test_pmd_feature_bytes_map_to_offline_data_types() -> None:
    async def run() -> None:
        feature_data = bytes((0x00, 0x06, 0x60))
        session = FakePmdSession(feature_data=feature_data)
        client = PmdClient(session, timeout_seconds=0.1)

        data_types = await client.get_available_offline_data_types()

        assert data_types == {
            PolarDeviceDataType.ACC,
            PolarDeviceDataType.PPG,
            PolarDeviceDataType.HR,
        }

    asyncio.run(run())


def test_pmd_feature_parser_rejects_malformed_data() -> None:
    try:
        parse_pmd_features(b"\x00\x01")
    except PmdProtocolError:
        pass
    else:
        raise AssertionError("Expected malformed PMD feature data to fail.")


def test_pmd_mapping_rejects_internal_or_unknown_types() -> None:
    try:
        map_pmd_to_polar(PmdMeasurementType.SDK_MODE)
    except PmdUnsupportedOperation:
        pass
    else:
        raise AssertionError("Expected SDK_MODE mapping to fail.")

    try:
        map_polar_to_pmd("not-a-data-type")
    except PmdUnsupportedOperation:
        pass
    else:
        raise AssertionError("Expected unknown data type mapping to fail.")


def test_pmd_settings_parse_and_serialize_selected_values() -> None:
    setting = PmdSetting.parse(
        bytes(
            (
                int(PmdSettingType.SAMPLE_RATE),
                2,
                50,
                0,
                100,
                0,
                int(PmdSettingType.CHANNELS),
                1,
                3,
            )
        )
    )

    assert setting.settings[PmdSettingType.SAMPLE_RATE] == {50, 100}
    assert setting.settings[PmdSettingType.CHANNELS] == {3}
    assert PmdSetting.from_selected(
        {
            PmdSettingType.SAMPLE_RATE: 50,
            PmdSettingType.RESOLUTION: 16,
            PmdSettingType.RANGE: 8,
            PmdSettingType.CHANNELS: 3,
        }
    ).serialize_selected() == bytes(
        (
            0,
            1,
            50,
            0,
            1,
            1,
            16,
            0,
            2,
            1,
            8,
            0,
            4,
            1,
            3,
        )
    )


def test_pmd_selected_settings_omit_response_only_fields() -> None:
    assert PmdSetting.from_selected(
        {
            PmdSettingType.SAMPLE_RATE: 50,
            PmdSettingType.FACTOR: 10,
        }
    ).serialize_selected() == bytes((0, 1, 50, 0))


def test_pmd_client_query_settings_uses_offline_request_bit() -> None:
    async def run() -> None:
        session = FakePmdSession()
        request = bytes(
            (
                int(PmdControlPointCommand.GET_MEASUREMENT_SETTINGS),
                PmdRecordingType.OFFLINE.bitfield | int(PmdMeasurementType.ACC),
            )
        )
        session.responses[request] = [
            cp_response(
                PmdControlPointCommand.GET_MEASUREMENT_SETTINGS,
                request[1],
                parameters=bytes((0, 1, 50, 0)),
            )
        ]
        client = PmdClient(session, timeout_seconds=0.1)

        setting = await client.query_settings(PmdMeasurementType.ACC)

        assert setting.settings[PmdSettingType.SAMPLE_RATE] == {50}
        assert session.writes[0] == (uuids.PMD_CONTROL_POINT, request, True)

    asyncio.run(run())


def test_pmd_client_chains_more_responses() -> None:
    async def run() -> None:
        session = FakePmdSession()
        request = bytes(
            (
                int(PmdControlPointCommand.GET_MEASUREMENT_SETTINGS),
                PmdRecordingType.OFFLINE.bitfield | int(PmdMeasurementType.ACC),
            )
        )
        session.responses[request] = [
            cp_response(
                PmdControlPointCommand.GET_MEASUREMENT_SETTINGS,
                request[1],
                parameters=bytes((0, 1)),
                more=True,
            ),
            cp_response(
                PmdControlPointCommand.GET_MEASUREMENT_SETTINGS,
                request[1],
                parameters=bytes((50, 0)),
            ),
        ]
        client = PmdClient(session, timeout_seconds=0.1)

        setting = await client.query_settings(PmdMeasurementType.ACC)

        assert setting.settings[PmdSettingType.SAMPLE_RATE] == {50}

    asyncio.run(run())


def test_pmd_client_response_error_preserves_response_code() -> None:
    async def run() -> None:
        session = FakePmdSession()
        request = bytes((int(PmdControlPointCommand.STOP_MEASUREMENT), 2))
        session.responses[request] = [
            cp_response(
                PmdControlPointCommand.STOP_MEASUREMENT,
                2,
                PmdResponseCode.ERROR_DISK_FULL,
            )
        ]
        client = PmdClient(session, timeout_seconds=0.1)

        try:
            await client.stop_measurement(PmdMeasurementType.ACC)
        except PmdResponseError as exc:
            assert exc.response_code == PmdResponseCode.ERROR_DISK_FULL
            assert exc.command == PmdControlPointCommand.STOP_MEASUREMENT
        else:
            raise AssertionError("Expected PMD response error.")

    asyncio.run(run())


def test_pmd_client_start_command_includes_offline_bit_and_settings() -> None:
    async def run() -> None:
        session = FakePmdSession()
        setting = PmdSetting.from_selected({"SAMPLE_RATE": 50, "CHANNELS": 3})
        request = bytes(
            (
                int(PmdControlPointCommand.REQUEST_MEASUREMENT_START),
                PmdRecordingType.OFFLINE.bitfield | int(PmdMeasurementType.ACC),
                0,
                1,
                50,
                0,
                4,
                1,
                3,
            )
        )
        session.responses[request] = [
            cp_response(
                PmdControlPointCommand.REQUEST_MEASUREMENT_START,
                request[1],
            )
        ]
        client = PmdClient(session, timeout_seconds=0.1)

        await client.start_measurement(PmdMeasurementType.ACC, setting)

        assert session.writes[-1] == (uuids.PMD_CONTROL_POINT, request, True)

    asyncio.run(run())


def test_pmd_client_status_maps_offline_active_states() -> None:
    async def run() -> None:
        session = FakePmdSession()
        request = bytes((int(PmdControlPointCommand.GET_MEASUREMENT_STATUS),))
        session.responses[request] = [
            cp_response(
                PmdControlPointCommand.GET_MEASUREMENT_STATUS,
                parameters=bytes(
                    (
                        0x80 | int(PmdMeasurementType.ACC),
                        0xC0 | int(PmdMeasurementType.PPG),
                        0x40 | int(PmdMeasurementType.GYRO),
                        0x80 | int(PmdMeasurementType.DERIVED_MEASUREMENT),
                    )
                ),
            )
        ]
        client = PmdClient(session, timeout_seconds=0.1)

        status = await client.read_measurement_status()

        assert status[PmdMeasurementType.ACC] == PmdActiveMeasurement.OFFLINE_MEASUREMENT_ACTIVE
        assert status[PmdMeasurementType.PPG] == PmdActiveMeasurement.ONLINE_AND_OFFLINE_ACTIVE
        assert status[PmdMeasurementType.GYRO] == PmdActiveMeasurement.ONLINE_MEASUREMENT_ACTIVE
        assert status[PmdMeasurementType.DERIVED_MEASUREMENT].is_offline_active is True

    asyncio.run(run())


def test_pmd_client_wait_for_inactive_polls_until_no_active_status() -> None:
    async def run() -> None:
        session = FakePmdSession()
        request = bytes((int(PmdControlPointCommand.GET_MEASUREMENT_STATUS),))
        session.responses[request] = [
            cp_response(
                PmdControlPointCommand.GET_MEASUREMENT_STATUS,
                parameters=bytes((0x80 | int(PmdMeasurementType.ACC),)),
            ),
            cp_response(
                PmdControlPointCommand.GET_MEASUREMENT_STATUS,
                parameters=bytes((int(PmdMeasurementType.ACC),)),
            ),
        ]
        client = PmdClient(session, timeout_seconds=0.1)

        await client.wait_for_measurement_inactive(
            PmdMeasurementType.ACC,
            poll_interval_seconds=0,
            timeout_seconds=0.5,
        )

        assert len(session.writes) == 2

    asyncio.run(run())


def test_pmd_client_wait_for_inactive_times_out() -> None:
    async def run() -> None:
        session = FakePmdSession()
        request = bytes((int(PmdControlPointCommand.GET_MEASUREMENT_STATUS),))
        session.responses[request] = [
            cp_response(
                PmdControlPointCommand.GET_MEASUREMENT_STATUS,
                parameters=bytes((0x80 | int(PmdMeasurementType.ACC),)),
            )
        ]
        client = PmdClient(session, timeout_seconds=0.1)

        try:
            await client.wait_for_measurement_inactive(
                PmdMeasurementType.ACC,
                poll_interval_seconds=0,
                timeout_seconds=0,
            )
        except PmdTimeoutError:
            pass
        else:
            raise AssertionError("Expected PMD timeout.")

    asyncio.run(run())


def test_pmd_client_trigger_set_reads_current_and_disables_unspecified() -> None:
    async def run() -> None:
        session = FakePmdSession()
        mode_request = bytes(
            (
                int(PmdControlPointCommand.SET_OFFLINE_RECORDING_TRIGGER_MODE),
                int(PmdOfflineRecTriggerMode.SYSTEM_START),
            )
        )
        status_request = bytes((int(PmdControlPointCommand.GET_OFFLINE_RECORDING_TRIGGER_STATUS),))
        enable_acc = bytes(
            (
                int(PmdControlPointCommand.SET_OFFLINE_RECORDING_TRIGGER_SETTINGS),
                int(PmdOfflineRecTriggerStatus.ENABLED),
                int(PmdMeasurementType.ACC),
                3,
                4,
                1,
                3,
            )
        )
        disable_ppg = bytes(
            (
                int(PmdControlPointCommand.SET_OFFLINE_RECORDING_TRIGGER_SETTINGS),
                int(PmdOfflineRecTriggerStatus.DISABLED),
                int(PmdMeasurementType.PPG),
            )
        )
        session.responses[mode_request] = [
            cp_response(PmdControlPointCommand.SET_OFFLINE_RECORDING_TRIGGER_MODE)
        ]
        session.responses[status_request] = [
            cp_response(
                PmdControlPointCommand.GET_OFFLINE_RECORDING_TRIGGER_STATUS,
                parameters=bytes(
                    (
                        int(PmdOfflineRecTriggerMode.SYSTEM_START),
                        int(PmdOfflineRecTriggerStatus.DISABLED),
                        int(PmdMeasurementType.ACC),
                        int(PmdOfflineRecTriggerStatus.DISABLED),
                        int(PmdMeasurementType.PPG),
                    )
                ),
            )
        ]
        session.responses[enable_acc] = [
            cp_response(PmdControlPointCommand.SET_OFFLINE_RECORDING_TRIGGER_SETTINGS)
        ]
        session.responses[disable_ppg] = [
            cp_response(PmdControlPointCommand.SET_OFFLINE_RECORDING_TRIGGER_SETTINGS)
        ]
        trigger = PmdOfflineTrigger(
            mode=PmdOfflineRecTriggerMode.SYSTEM_START,
            triggers={
                PmdMeasurementType.ACC: (
                    PmdOfflineRecTriggerStatus.ENABLED,
                    PmdSetting.from_selected({"CHANNELS": 3}),
                )
            },
        )
        client = PmdClient(session, timeout_seconds=0.1)

        await client.set_offline_recording_trigger(trigger)

        assert [write[1] for write in session.writes] == [
            mode_request,
            status_request,
            enable_acc,
            disable_ppg,
        ]

    asyncio.run(run())
