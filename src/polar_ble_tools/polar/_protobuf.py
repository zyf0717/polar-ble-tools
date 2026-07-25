from __future__ import annotations

from dataclasses import dataclass


class ProtobufDecodeError(ValueError):
    """Raised when the small PFTP protobuf subset cannot be decoded."""


def encode_varint(value: int) -> bytes:
    if value < 0:
        raise ValueError("Only unsigned varints are supported.")
    output = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            output.append(byte | 0x80)
        else:
            output.append(byte)
            return bytes(output)


def decode_varint(data: bytes, offset: int = 0) -> tuple[int, int]:
    shift = 0
    result = 0
    while offset < len(data):
        byte = data[offset]
        offset += 1
        result |= (byte & 0x7F) << shift
        if byte < 0x80:
            return result, offset
        shift += 7
        if shift >= 64:
            raise ProtobufDecodeError("Varint is too long.")
    raise ProtobufDecodeError("Unexpected end of data while decoding varint.")


def encode_key(field_number: int, wire_type: int) -> bytes:
    return encode_varint((field_number << 3) | wire_type)


def encode_uint64(field_number: int, value: int) -> bytes:
    return encode_key(field_number, 0) + encode_varint(value)


def encode_bool(field_number: int, value: bool) -> bytes:
    return encode_key(field_number, 0) + encode_varint(1 if value else 0)


def encode_string(field_number: int, value: str) -> bytes:
    encoded = value.encode("utf-8")
    return encode_key(field_number, 2) + encode_varint(len(encoded)) + encoded


def read_length_delimited(data: bytes, offset: int) -> tuple[bytes, int]:
    length, offset = decode_varint(data, offset)
    end = offset + length
    if end > len(data):
        raise ProtobufDecodeError("Length-delimited field exceeds input size.")
    return data[offset:end], end


def skip_field(data: bytes, offset: int, wire_type: int) -> int:
    if wire_type == 0:
        _, offset = decode_varint(data, offset)
        return offset
    if wire_type == 1:
        return offset + 8
    if wire_type == 2:
        _, offset = read_length_delimited(data, offset)
        return offset
    if wire_type == 5:
        return offset + 4
    raise ProtobufDecodeError(f"Unsupported protobuf wire type: {wire_type}")


class PftpCommand:
    GET = 0
    PUT = 1
    MERGE = 2
    REMOVE = 3


@dataclass(frozen=True)
class PftpDirectoryEntry:
    name: str
    size: int


@dataclass(frozen=True)
class PftpDiskSpace:
    fragment_size: int
    total_fragments: int
    free_fragments: int

    @property
    def total_bytes(self) -> int:
        return self.fragment_size * self.total_fragments

    @property
    def free_bytes(self) -> int:
        return self.fragment_size * self.free_fragments

    @property
    def used_bytes(self) -> int:
        return self.total_bytes - self.free_bytes

    def to_jsonable(self) -> dict[str, int]:
        return {
            "fragment_size": self.fragment_size,
            "free_bytes": self.free_bytes,
            "free_fragments": self.free_fragments,
            "total_bytes": self.total_bytes,
            "total_fragments": self.total_fragments,
            "used_bytes": self.used_bytes,
        }


def encode_pftp_operation(command: int, path: str) -> bytes:
    return encode_uint64(1, command) + encode_string(2, path)


def decode_pftp_entry(data: bytes) -> PftpDirectoryEntry:
    offset = 0
    name: str | None = None
    size: int | None = None
    while offset < len(data):
        key, offset = decode_varint(data, offset)
        field_number = key >> 3
        wire_type = key & 0x07
        if field_number == 1 and wire_type == 2:
            raw, offset = read_length_delimited(data, offset)
            name = raw.decode("utf-8")
        elif field_number == 2 and wire_type == 0:
            size, offset = decode_varint(data, offset)
        else:
            raise ProtobufDecodeError(
                f"Unknown PFTP directory-entry field {field_number} (wire type {wire_type})."
            )
    if name is None or size is None:
        raise ProtobufDecodeError("PFTP directory entry is missing name or size.")
    return PftpDirectoryEntry(name=name, size=size)


def decode_pftp_directory(data: bytes) -> list[PftpDirectoryEntry]:
    offset = 0
    entries: list[PftpDirectoryEntry] = []
    while offset < len(data):
        key, offset = decode_varint(data, offset)
        field_number = key >> 3
        wire_type = key & 0x07
        if field_number == 1 and wire_type == 2:
            raw, offset = read_length_delimited(data, offset)
            entries.append(decode_pftp_entry(raw))
        else:
            raise ProtobufDecodeError(
                f"Unknown PFTP directory field {field_number} (wire type {wire_type})."
            )
    return entries


def decode_pftp_disk_space(data: bytes) -> PftpDiskSpace:
    offset = 0
    fragment_size: int | None = None
    total_fragments: int | None = None
    free_fragments: int | None = None
    while offset < len(data):
        key, offset = decode_varint(data, offset)
        field_number = key >> 3
        wire_type = key & 0x07
        if field_number == 1 and wire_type == 0:
            fragment_size, offset = decode_varint(data, offset)
        elif field_number == 2 and wire_type == 0:
            total_fragments, offset = decode_varint(data, offset)
        elif field_number == 3 and wire_type == 0:
            free_fragments, offset = decode_varint(data, offset)
        else:
            raise ProtobufDecodeError(
                f"Unknown PFTP disk-space field {field_number} (wire type {wire_type})."
            )
    if fragment_size is None:
        raise ProtobufDecodeError("PFTP disk-space response is missing fragment size.")
    if total_fragments is None:
        raise ProtobufDecodeError("PFTP disk-space response is missing total fragments.")
    if free_fragments is None:
        raise ProtobufDecodeError("PFTP disk-space response is missing free fragments.")
    return PftpDiskSpace(
        fragment_size=fragment_size,
        total_fragments=total_fragments,
        free_fragments=free_fragments,
    )


def encode_pftp_entry(entry: PftpDirectoryEntry) -> bytes:
    return encode_string(1, entry.name) + encode_uint64(2, entry.size)


def encode_pftp_directory(entries: list[PftpDirectoryEntry]) -> bytes:
    output = bytearray()
    for entry in entries:
        encoded = encode_pftp_entry(entry)
        output += encode_key(1, 2) + encode_varint(len(encoded)) + encoded
    return bytes(output)
