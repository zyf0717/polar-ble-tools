from __future__ import annotations

from google.protobuf.descriptor import FieldDescriptor

from polar_ble_tools.bpb_decode import SUPPORTED_STATUS, decode_bpb_file
from polar_ble_tools.bpb_decode.schemas import BPB_SCHEMAS
from polar_ble_tools.schemas import require_modules


def test_bpb_decoder_uses_active_generated_schema_cache(tmp_path) -> None:
    modules = require_modules("dailysummary_pb2", "types_pb2")
    payload = modules.dailysummary_pb2.PbDailySummary(
        date=modules.types_pb2.PbDate(year=2026, month=6, day=25),
        steps=123,
    ).SerializeToString()
    path = tmp_path / "DSUM.BPB"
    path.write_bytes(payload)

    result = decode_bpb_file(path, device_path="/U/0/20260625/DSUM/DSUM.BPB")

    assert result.status == SUPPORTED_STATUS
    assert result.schema_id == "daily_summary"
    assert result.message_type == "data.PbDailySummary"
    assert result.data == {"date": {"year": 2026, "month": 6, "day": 25}, "steps": 123}


def test_every_registered_bpb_schema_round_trips_with_official_bindings() -> None:
    for schema in BPB_SCHEMAS:
        message = schema.message_class()
        _initialize_required_fields(message, set())
        assert message.IsInitialized(), (
            schema.schema_id,
            message.FindInitializationErrors(),
        )
        encoded = message.SerializeToString()
        decoded = schema.message_class()
        decoded.ParseFromString(encoded)
        assert decoded.IsInitialized(), schema.schema_id
        assert decoded.SerializeToString() == encoded


def _initialize_required_fields(message, visiting: set[str]) -> None:
    descriptor = message.DESCRIPTOR
    if descriptor.full_name in visiting:
        return
    visiting.add(descriptor.full_name)
    for field in descriptor.fields:
        if not field.is_required:
            continue
        if field.cpp_type == FieldDescriptor.CPPTYPE_MESSAGE:
            child = getattr(message, field.name)
            child.SetInParent()
            _initialize_required_fields(child, visiting)
        elif field.cpp_type == FieldDescriptor.CPPTYPE_ENUM:
            setattr(message, field.name, field.enum_type.values[0].number)
        elif field.cpp_type == FieldDescriptor.CPPTYPE_STRING:
            value = b"" if field.type == FieldDescriptor.TYPE_BYTES else ""
            setattr(message, field.name, value)
        elif field.cpp_type == FieldDescriptor.CPPTYPE_BOOL:
            setattr(message, field.name, False)
        elif field.cpp_type in {
            FieldDescriptor.CPPTYPE_FLOAT,
            FieldDescriptor.CPPTYPE_DOUBLE,
        }:
            setattr(message, field.name, 0.0)
        else:
            setattr(message, field.name, 0)
    visiting.remove(descriptor.full_name)
