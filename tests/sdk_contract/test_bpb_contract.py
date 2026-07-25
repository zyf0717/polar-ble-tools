from __future__ import annotations

from polar_ble_tools.bpb_decode import SUPPORTED_STATUS, decode_bpb_file
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
