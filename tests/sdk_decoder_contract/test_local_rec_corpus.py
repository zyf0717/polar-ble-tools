"""Opt-in contracts for local, non-redistributable REC fixtures."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from polar_ble_tools.rec import decode_recording, decoder_status, iter_decoded_records

_PPI_TIMESTAMP_WARNING = "PPI timestamps are intentionally omitted pending validated SDK semantics"

pytestmark = pytest.mark.skipif(
    os.environ.get("POLAR_BLE_SDK_DECODER_CONTRACT") != "1",
    reason="set POLAR_BLE_SDK_DECODER_CONTRACT=1 with a local REC fixture root",
)


def test_local_rec_corpus_is_deterministic(tmp_path: Path) -> None:
    manifest_text = os.environ.get("POLAR_BLE_REC_FIXTURE_MANIFEST")
    assert manifest_text, "set POLAR_BLE_REC_FIXTURE_MANIFEST to a private fixture manifest"
    manifest_path = Path(manifest_text)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    fixtures = manifest.get("fixtures")
    assert isinstance(fixtures, list) and fixtures, (
        "fixture manifest must contain a non-empty fixtures array"
    )
    assert decoder_status().available, "build and activate the local REC decoder first"

    for index, fixture in enumerate(fixtures):
        assert isinstance(fixture, dict)
        relative = fixture.get("path")
        record_type = fixture.get("record_type")
        expected_count = fixture.get("record_count")
        source_digest = fixture.get("source_sha256")
        output_digest = fixture.get("expected_output_sha256")
        assert all(
            isinstance(value, str)
            for value in (relative, record_type, source_digest, output_digest)
        )
        assert isinstance(expected_count, int) and expected_count >= 0
        source = manifest_path.parent / relative
        assert source.is_file(), f"missing local fixture: {relative}"
        assert hashlib.sha256(source.read_bytes()).hexdigest() == source_digest
        first, second = tmp_path / f"{index}-one.jsonl", tmp_path / f"{index}-two.jsonl"
        first_report = decode_recording(source, first)
        second_report = decode_recording(source, second)
        assert (first_report.record_types, first_report.record_count) == (
            {record_type: expected_count},
            expected_count,
        )
        assert second_report.destination_sha256 == first_report.destination_sha256
        assert first_report.destination_sha256 == output_digest
        assert second.read_bytes() == first.read_bytes()
        if record_type == "ppi":
            records = list(iter_decoded_records(first))
            assert records
            assert all(record.timestamp_ns is None for record in records)
            assert all("time_stamp" in record.payload["sample"] for record in records)
            assert first_report.warnings.count(_PPI_TIMESTAMP_WARNING) == 1
