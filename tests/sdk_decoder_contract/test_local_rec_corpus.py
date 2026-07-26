"""Opt-in contracts for local, non-redistributable REC fixtures."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from polar_ble_tools.rec import decode_recording, decoder_status

pytestmark = pytest.mark.skipif(
    os.environ.get("POLAR_BLE_SDK_DECODER_CONTRACT") != "1",
    reason="set POLAR_BLE_SDK_DECODER_CONTRACT=1 with a local REC fixture root",
)

_EXPECTED = {
    "loop_gen2/U0/20260625/142508/ACC0.REC": ("acc", 377),
    "loop_gen2/U0/20260625/142509/HR0.REC": ("hr", 5),
    "loop_gen2/U0/20260625/142509/PPG0.REC": ("ppg", 188),
    "loop_gen2/U0/20260625/142509/PPI0.REC": ("ppi", 7),
    "loop_gen2/U0/20260625/142510/SKINTEMP0.REC": ("skin_temperature", 5),
    "verity/U0/20260626/143133/MAG.REC": ("mag", 40),
    "verity/U0/20260626/144529/GYRO.REC": ("gyro", 40),
    "verity/U0/20260626/144616/PPI.REC": ("ppi", 30),
    "verity/U0/20260626/144730/PPG.REC": ("ppg", 440),
}


def test_local_rec_corpus_is_deterministic(tmp_path: Path) -> None:
    root_text = os.environ.get("POLAR_BLE_REC_FIXTURES")
    assert root_text, "set POLAR_BLE_REC_FIXTURES to the local REC fixture root"
    root = Path(root_text)
    assert decoder_status().available, "build and activate the local REC decoder first"

    for index, (relative, (record_type, expected_count)) in enumerate(_EXPECTED.items()):
        source = root / relative
        assert source.is_file(), f"missing local fixture: {relative}"
        first, second = tmp_path / f"{index}-one.jsonl", tmp_path / f"{index}-two.jsonl"
        first_report = decode_recording(source, first)
        second_report = decode_recording(source, second)
        assert (first_report.record_types, first_report.record_count) == ({record_type: expected_count}, expected_count)
        assert second_report.destination_sha256 == first_report.destination_sha256
        assert second.read_bytes() == first.read_bytes()
