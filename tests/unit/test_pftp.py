import asyncio

import pytest

from polar_ble_tools.polar import uuids
from polar_ble_tools.polar._protobuf import (
    PftpCommand,
    PftpDirectoryEntry,
    ProtobufDecodeError,
    decode_pftp_directory,
    decode_pftp_disk_space,
    encode_pftp_directory,
    encode_pftp_operation,
    encode_uint64,
)
from polar_ble_tools.polar.pftp import (
    PftpClient,
    PftpHostNotification,
    PftpQuery,
    build_rfc76_frames,
    make_complete_message,
    parse_rfc76_frame,
)


class FakePftpSession:
    is_connected = True
    services = [uuids.PFTP_SERVICE]

    def __init__(self, response_payload: bytes) -> None:
        self.response_frames = build_rfc76_frames(response_payload, mtu_size=8)
        self.notify_callbacks = {}
        self.writes: list[tuple[str, bytes, bool]] = []

    async def disconnect(self) -> None:
        self.is_connected = False

    async def read(self, characteristic_uuid: str) -> bytes:
        raise AssertionError(f"Unexpected read: {characteristic_uuid}")

    async def write(
        self,
        characteristic_uuid: str,
        data: bytes,
        *,
        response: bool = False,
    ) -> None:
        self.writes.append((characteristic_uuid, data, response))
        if characteristic_uuid == uuids.PFTP_MTU:
            callback = self.notify_callbacks[uuids.PFTP_MTU]
            for frame in self.response_frames:
                callback(uuids.PFTP_MTU, frame)

    async def start_notify(self, characteristic_uuid: str, callback) -> None:
        self.notify_callbacks[characteristic_uuid] = callback

    async def stop_notify(self, characteristic_uuid: str) -> None:
        self.notify_callbacks.pop(characteristic_uuid, None)


def test_pftp_operation_codec_matches_sdk_proto_shape() -> None:
    assert encode_pftp_operation(PftpCommand.GET, "/U/0/") == b"\x08\x00\x12\x05/U/0/"


def test_pftp_directory_codec_round_trips_entries() -> None:
    entries = [PftpDirectoryEntry(name="ACC.REC", size=123)]

    assert decode_pftp_directory(encode_pftp_directory(entries)) == entries


def test_pftp_disk_space_codec_decodes_fragment_counters() -> None:
    disk_space = decode_pftp_disk_space(
        encode_uint64(1, 1024) + encode_uint64(2, 100) + encode_uint64(3, 25)
    )

    assert disk_space.fragment_size == 1024
    assert disk_space.total_fragments == 100
    assert disk_space.free_fragments == 25
    assert disk_space.total_bytes == 102400
    assert disk_space.free_bytes == 25600
    assert disk_space.used_bytes == 76800


def test_manual_pftp_decoder_rejects_unknown_and_truncated_wire_data() -> None:
    with pytest.raises(ProtobufDecodeError):
        decode_pftp_directory(b"\x0a\x05\x0a")
    with pytest.raises(ProtobufDecodeError):
        decode_pftp_disk_space(b"\x20\x01")


def test_pftp_client_lists_directory_with_rfc76_response_frames() -> None:
    async def run() -> None:
        directory_bytes = encode_pftp_directory([PftpDirectoryEntry(name="20260613", size=0)])
        session = FakePftpSession(directory_bytes)
        client = PftpClient(session, mtu_size=8, timeout_seconds=0.1)

        entries = await client.list_directory("/U/0/")

        assert entries == [PftpDirectoryEntry(name="20260613", size=0)]
        assert session.writes[0][0] == uuids.PFTP_MTU
        assert session.writes[0][2] is False

    asyncio.run(run())


def test_pftp_client_get_disk_space_uses_query_shape() -> None:
    async def run() -> None:
        payload = encode_uint64(1, 512) + encode_uint64(2, 20) + encode_uint64(3, 5)
        session = FakePftpSession(payload)
        client = PftpClient(session, mtu_size=64, timeout_seconds=0.1)

        disk_space = await client.get_disk_space()

        frame = parse_rfc76_frame(session.writes[0][1])
        assert frame.payload == make_complete_message(
            None,
            query_id=PftpQuery.GET_DISK_SPACE,
        )
        assert disk_space.to_jsonable() == {
            "fragment_size": 512,
            "free_bytes": 2560,
            "free_fragments": 5,
            "total_bytes": 10240,
            "total_fragments": 20,
            "used_bytes": 7680,
        }

    asyncio.run(run())


def test_pftp_client_put_file_uses_put_operation_and_payload() -> None:
    async def run() -> None:
        session = FakePftpSession(b"")
        client = PftpClient(session, mtu_size=64, timeout_seconds=0.1)

        await client.put_file("/U/0/S/PHYSDATA.BPB", b"profile")

        frame = parse_rfc76_frame(session.writes[0][1])
        header = encode_pftp_operation(PftpCommand.PUT, "/U/0/S/PHYSDATA.BPB")
        assert frame.payload == make_complete_message(header, b"profile")

    asyncio.run(run())


def test_pftp_client_remove_file_uses_remove_operation() -> None:
    async def run() -> None:
        session = FakePftpSession(b"")
        client = PftpClient(session, mtu_size=64, timeout_seconds=0.1)

        await client.remove_file("/U/0/20260613/R/112233/ACC.REC")

        frame = parse_rfc76_frame(session.writes[0][1])
        assert frame.payload == make_complete_message(
            encode_pftp_operation(
                PftpCommand.REMOVE,
                "/U/0/20260613/R/112233/ACC.REC",
            )
        )

    asyncio.run(run())


def test_pftp_client_query_uses_query_message_shape() -> None:
    async def run() -> None:
        session = FakePftpSession(b"")
        client = PftpClient(session, mtu_size=64, timeout_seconds=0.1)

        await client.query(PftpQuery.SET_LOCAL_TIME, b"\x08\x01")

        frame = parse_rfc76_frame(session.writes[0][1])
        assert frame.payload == make_complete_message(
            b"\x08\x01",
            query_id=PftpQuery.SET_LOCAL_TIME,
        )

    asyncio.run(run())


def test_pftp_sync_notification_helpers_match_sdk_order() -> None:
    async def run() -> None:
        session = FakePftpSession(b"")
        client = PftpClient(session, mtu_size=64, timeout_seconds=0.1)

        await client.send_initialization_and_start_sync_notifications()
        await client.send_terminate_and_stop_sync_notifications()

        writes = [
            (characteristic, parse_rfc76_frame(data).payload)
            for characteristic, data, _response in session.writes
        ]
        assert writes == [
            (
                uuids.PFTP_MTU,
                make_complete_message(
                    None,
                    query_id=PftpQuery.REQUEST_SYNCHRONIZATION,
                ),
            ),
            (
                uuids.PFTP_HOST_TO_DEVICE,
                make_complete_message(
                    None,
                    notification_id=PftpHostNotification.INITIALIZE_SESSION,
                ),
            ),
            (
                uuids.PFTP_HOST_TO_DEVICE,
                make_complete_message(
                    None,
                    notification_id=PftpHostNotification.START_SYNC,
                ),
            ),
            (
                uuids.PFTP_HOST_TO_DEVICE,
                make_complete_message(
                    b"\x08\x01",
                    notification_id=PftpHostNotification.STOP_SYNC,
                ),
            ),
            (
                uuids.PFTP_HOST_TO_DEVICE,
                make_complete_message(
                    None,
                    notification_id=PftpHostNotification.TERMINATE_SESSION,
                ),
            ),
        ]

    asyncio.run(run())
