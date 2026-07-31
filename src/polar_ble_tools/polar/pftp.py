from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum

from polar_ble_tools.ble.transport import BleServiceNotFound, BleSession, LifecyclePhase
from polar_ble_tools.polar import uuids
from polar_ble_tools.polar._protobuf import (
    PftpCommand,
    PftpDirectoryEntry,
    PftpDiskSpace,
    decode_pftp_directory,
    decode_pftp_disk_space,
    encode_bool,
    encode_pftp_operation,
)

ProgressCallback = Callable[[int], None]

RFC76_HEADER_SIZE = 1
RFC76_STATUS_ERROR_OR_RESPONSE = 0x00
RFC76_STATUS_LAST = 0x01
RFC76_STATUS_MORE = 0x03
DEFAULT_MTU_SIZE = 20
DEFAULT_TIMEOUT_SECONDS = 90.0


class PftpError(RuntimeError):
    """Base PFTP error."""


class PftpProtocolError(PftpError):
    """Raised on RFC76/RFC60 protocol errors."""


class PftpResponseError(PftpError):
    def __init__(self, message: str, error_code: int) -> None:
        self.error_code = error_code
        super().__init__(f"{message}: {error_code}")


class PftpTimeoutError(PftpError):
    """Raised when a PFTP packet is not received in time."""


class PftpHostNotification(IntEnum):
    START_SYNC = 0
    STOP_SYNC = 1
    RESET = 2
    INITIALIZE_SESSION = 8
    TERMINATE_SESSION = 9


class PftpQuery(IntEnum):
    SET_SYSTEM_TIME = 1
    SET_LOCAL_TIME = 3
    GET_LOCAL_TIME = 4
    GET_DISK_SPACE = 5
    REQUEST_SYNCHRONIZATION = 13


@dataclass(frozen=True)
class Rfc76Frame:
    next: int
    status: int
    sequence_number: int
    payload: bytes
    error: int | None = None


def make_complete_message(
    header: bytes | None,
    data: bytes | None = None,
    *,
    query_id: int | None = None,
    notification_id: int | None = None,
) -> bytes:
    if query_id is not None and notification_id is not None:
        raise ValueError("query_id and notification_id are mutually exclusive.")
    if notification_id is not None:
        return bytes([notification_id]) + (header or b"")
    if query_id is not None:
        return (query_id | 0x8000).to_bytes(2, "little") + (header or b"")
    header = header or b""
    return len(header).to_bytes(2, "little") + header + (data or b"")


def build_rfc76_frames(
    payload: bytes,
    *,
    mtu_size: int = DEFAULT_MTU_SIZE,
) -> list[bytes]:
    if mtu_size <= RFC76_HEADER_SIZE:
        raise ValueError("mtu_size must leave room for an RFC76 payload.")
    frames: list[bytes] = []
    sequence = 0
    next_bit = 0
    offset = 0
    chunk_size = mtu_size - RFC76_HEADER_SIZE
    while offset < len(payload) or not frames:
        chunk = payload[offset : offset + chunk_size]
        offset += len(chunk)
        status_bits = 0x06 if offset < len(payload) else 0x02
        header = next_bit | status_bits | (sequence << 4)
        frames.append(bytes([header]) + chunk)
        next_bit = 1
        sequence = (sequence + 1) & 0x0F
    return frames


def parse_rfc76_frame(packet: bytes) -> Rfc76Frame:
    if len(packet) < RFC76_HEADER_SIZE:
        raise PftpProtocolError("Empty RFC76 packet.")
    header = packet[0]
    next_bit = header & 0x01
    status = (header >> 1) & 0x03
    sequence_number = (header >> 4) & 0x0F
    if status == RFC76_STATUS_ERROR_OR_RESPONSE:
        if len(packet) < 3:
            raise PftpProtocolError("PFTP error frame is missing error code.")
        error = packet[1] | (packet[2] << 8)
        return Rfc76Frame(
            next=next_bit,
            status=status,
            sequence_number=sequence_number,
            payload=b"",
            error=error,
        )
    return Rfc76Frame(
        next=next_bit,
        status=status,
        sequence_number=sequence_number,
        payload=packet[1:],
    )


class PftpClient:
    def __init__(
        self,
        session: BleSession,
        *,
        mtu_size: int = DEFAULT_MTU_SIZE,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.session = session
        self.mtu_size = mtu_size
        self.timeout_seconds = timeout_seconds
        self._mtu_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._request_lock = asyncio.Lock()
        self._response_may_be_stale = False
        self._notifications_started = False

    def ensure_pftp_service(self) -> None:
        normalized = {service.lower() for service in self.session.services}
        if normalized and not normalized.intersection(uuids.PFTP_SERVICE_ALIASES):
            raise BleServiceNotFound(
                LifecyclePhase.SERVICE_READINESS,
                "Polar PFTP service was not discovered.",
            )

    async def start_notifications(self) -> None:
        if self._notifications_started:
            return
        self.ensure_pftp_service()
        await self.session.start_notify(uuids.PFTP_MTU, self._on_mtu_packet)
        await self.session.start_notify(uuids.PFTP_DEVICE_TO_HOST, self._on_device_packet)
        self._notifications_started = True

    async def stop_notifications(self) -> None:
        if not self._notifications_started:
            return
        await self.session.stop_notify(uuids.PFTP_MTU)
        await self.session.stop_notify(uuids.PFTP_DEVICE_TO_HOST)
        self._notifications_started = False

    def _on_mtu_packet(self, _sender: str, data: bytes) -> None:
        self._mtu_queue.put_nowait(data)

    def _on_device_packet(self, _sender: str, _data: bytes) -> None:
        return

    async def request(
        self,
        header: bytes,
        data: bytes | None = None,
        *,
        progress: ProgressCallback | None = None,
    ) -> bytes:
        async with self._request_lock:
            await self.start_notifications()
            self._discard_stale_responses()
            payload = make_complete_message(header, data)
            try:
                return await self._write_and_read(payload, progress=progress)
            except BaseException:
                self._response_may_be_stale = True
                raise

    async def query(
        self,
        query: PftpQuery | int,
        parameters: bytes | None = None,
        *,
        progress: ProgressCallback | None = None,
    ) -> bytes:
        async with self._request_lock:
            await self.start_notifications()
            self._discard_stale_responses()
            payload = make_complete_message(parameters, query_id=int(query))
            try:
                return await self._write_and_read(payload, progress=progress)
            except BaseException:
                self._response_may_be_stale = True
                raise

    async def _write_and_read(
        self,
        payload: bytes,
        *,
        progress: ProgressCallback | None = None,
    ) -> bytes:
        frames = build_rfc76_frames(payload, mtu_size=self.mtu_size)
        written = 0
        for frame in frames:
            await self.session.write(uuids.PFTP_MTU, frame, response=False)
            written += len(frame)
            if progress is not None:
                progress(written)
        return await self._read_response()

    async def send_host_notification(
        self,
        notification: PftpHostNotification,
        parameters: bytes | None = None,
    ) -> None:
        async with self._request_lock:
            await self.start_notifications()
            payload = make_complete_message(
                parameters,
                notification_id=int(notification),
            )
            for frame in build_rfc76_frames(payload, mtu_size=self.mtu_size):
                await self.session.write(uuids.PFTP_HOST_TO_DEVICE, frame, response=False)

    def _discard_stale_responses(self) -> None:
        if not self._response_may_be_stale:
            return
        self._response_may_be_stale = False
        while True:
            try:
                self._mtu_queue.get_nowait()
            except asyncio.QueueEmpty:
                return

    async def list_directory(self, path: str) -> list[PftpDirectoryEntry]:
        response = await self.request(encode_pftp_operation(PftpCommand.GET, path))
        return decode_pftp_directory(response)

    async def get_file(
        self,
        path: str,
        *,
        progress: ProgressCallback | None = None,
    ) -> bytes:
        return await self.request(
            encode_pftp_operation(PftpCommand.GET, path),
            progress=progress,
        )

    async def get_disk_space(self) -> PftpDiskSpace:
        response = await self.query(PftpQuery.GET_DISK_SPACE)
        return decode_pftp_disk_space(response)

    async def put_file(
        self,
        path: str,
        data: bytes,
        *,
        progress: ProgressCallback | None = None,
    ) -> None:
        await self.request(
            encode_pftp_operation(PftpCommand.PUT, path),
            data,
            progress=progress,
        )

    async def remove_file(self, path: str) -> None:
        await self.request(encode_pftp_operation(PftpCommand.REMOVE, path))

    async def send_initialization_and_start_sync_notifications(self) -> None:
        await self.query(PftpQuery.REQUEST_SYNCHRONIZATION)
        await self.send_host_notification(PftpHostNotification.INITIALIZE_SESSION)
        await self.send_host_notification(PftpHostNotification.START_SYNC)

    async def send_terminate_and_stop_sync_notifications(
        self,
        *,
        completed: bool = True,
    ) -> None:
        await self.send_host_notification(
            PftpHostNotification.STOP_SYNC,
            encode_bool(1, completed),
        )
        await self.send_host_notification(PftpHostNotification.TERMINATE_SESSION)

    async def _read_response(self) -> bytes:
        chunks = bytearray()
        expected_sequence = 0
        expected_next = 0
        while True:
            try:
                packet = await asyncio.wait_for(
                    self._mtu_queue.get(),
                    timeout=self.timeout_seconds,
                )
            except TimeoutError as exc:
                raise PftpTimeoutError("Timed out waiting for PFTP response.") from exc
            frame = parse_rfc76_frame(packet)
            if frame.sequence_number != expected_sequence:
                raise PftpProtocolError("PFTP response sequence number mismatch.")
            if frame.next != expected_next:
                raise PftpProtocolError("PFTP response stream is out of sync.")
            expected_sequence = (expected_sequence + 1) & 0x0F
            expected_next = 1
            if frame.status == RFC76_STATUS_ERROR_OR_RESPONSE:
                if frame.error == 0:
                    return bytes(chunks)
                raise PftpResponseError("PFTP request failed", frame.error or 0)
            if frame.status in {RFC76_STATUS_MORE, RFC76_STATUS_LAST}:
                chunks.extend(frame.payload)
                if frame.status == RFC76_STATUS_LAST:
                    return bytes(chunks)
                continue
            raise PftpProtocolError(f"Unknown PFTP frame status: {frame.status}")
