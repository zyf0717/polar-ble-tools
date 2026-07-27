from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from polar_ble_tools.ble.transport import BleConnectionError
from polar_ble_tools.polar.offline import (
    DeviceDeletionResult,
    OfflineRecord,
    base_record_type_for,
    parse_offline_recording_path,
    record_type_matches_deletion_family,
)
from polar_ble_tools.polar.pmd import PolarDeviceDataType
from polar_ble_tools.raw_data.collector import RawRecordingCollector
from polar_ble_tools.raw_data.storage import RawRecordingStore


class FakeOfflineClient:
    def __init__(self, *, fail_paths: set[str] | None = None) -> None:
        self.entries = [
            parse_offline_recording_path("/U/0/20260725/R/112233/ACC0.REC", size=9),
            parse_offline_recording_path("/U/0/20260725/R/112244/PPG.REC", size=8),
        ]
        self.fail_paths = fail_paths or set()
        self.fetches: list[str] = []
        self.removed: list[str] = []

    async def list_recording_files(self):
        return self.entries

    async def fetch_record(self, entry):
        self.fetches.append(entry.path)
        if entry.path in self.fail_paths:
            raise RuntimeError("fetch failed")
        return OfflineRecord(entry, f"{entry.record_type}-data".encode())

    async def list_record_family(self, entry):
        return [
            candidate
            for candidate in self.entries
            if record_type_matches_deletion_family(entry.record_type, candidate.record_type)
        ]

    async def remove_record(self, entry, *, dry_run=False):
        family = await self.list_record_family(entry)
        paths = [item.path for item in family]
        if not dry_run:
            self.removed.extend(paths)
        return DeviceDeletionResult(
            entry.path,
            entry.record_type,
            base_record_type_for(entry.record_type),
            "dry_run" if dry_run else "deleted",
            paths,
            [],
        )


class FakeControlClient:
    def __init__(self, status=None, error: Exception | None = None) -> None:
        self.status = status or {}
        self.error = error

    async def get_recording_status(self):
        if self.error:
            raise self.error
        return self.status


def test_collector_fetches_filters_and_hash_skips(tmp_path: Path) -> None:
    async def run() -> None:
        store = RawRecordingStore(tmp_path / "raw")
        first_client = FakeOfflineClient()
        first = RawRecordingCollector(first_client, store)  # type: ignore[arg-type]
        result = await first.collect("AA:BB:CC:DD:EE:FF", record_types={"ACC"})
        assert (result.fetched, result.ignored, result.failed) == (1, 1, 0)
        assert first_client.fetches == ["/U/0/20260725/R/112233/ACC0.REC"]

        second_client = FakeOfflineClient()
        second = RawRecordingCollector(second_client, store)  # type: ignore[arg-type]
        rerun = await second.collect("AA:BB:CC:DD:EE:FF", record_types={"ACC"})
        assert (rerun.skipped, rerun.ignored) == (1, 1)
        assert second_client.fetches == []

    asyncio.run(run())


def test_collect_delete_requires_verified_inactive_copy(tmp_path: Path) -> None:
    async def run() -> None:
        client = FakeOfflineClient()
        collector = RawRecordingCollector(client, RawRecordingStore(tmp_path / "raw"))  # type: ignore[arg-type]
        result = await collector.collect(
            "AA:BB:CC:DD:EE:FF",
            record_types={"ACC"},
            delete_after_collect=True,
            control_client=FakeControlClient({PolarDeviceDataType.ACC: False}),  # type: ignore[arg-type]
        )
        assert result.deleted == 1
        assert result.records[0].delete_status == "deleted"
        assert client.removed == ["/U/0/20260725/R/112233/ACC0.REC"]

    asyncio.run(run())


def test_cleanup_blocks_active_or_unverified_records(tmp_path: Path) -> None:
    async def run() -> None:
        client = FakeOfflineClient()
        collector = RawRecordingCollector(client, RawRecordingStore(tmp_path / "raw"))  # type: ignore[arg-type]
        unverified = await collector.cleanup(
            "AA:BB:CC:DD:EE:FF",
            record_types={"ACC"},
            control_client=FakeControlClient(),  # type: ignore[arg-type]
        )
        assert unverified.records[0].status == "blocked_unverified"

        await collector.collect("AA:BB:CC:DD:EE:FF", record_types={"ACC"})
        active = await collector.cleanup(
            "AA:BB:CC:DD:EE:FF",
            record_types={"ACC"},
            control_client=FakeControlClient({PolarDeviceDataType.ACC: True}),  # type: ignore[arg-type]
        )
        assert active.records[0].status == "blocked_active"
        assert client.removed == []

    asyncio.run(run())


def test_cleanup_dry_run_never_removes_device_files(tmp_path: Path) -> None:
    async def run() -> None:
        client = FakeOfflineClient()
        collector = RawRecordingCollector(client, RawRecordingStore(tmp_path / "raw"))  # type: ignore[arg-type]
        await collector.collect("AA:BB:CC:DD:EE:FF", record_types={"ACC"})
        result = await collector.cleanup("AA:BB:CC:DD:EE:FF", record_types={"ACC"}, dry_run=True)
        assert result.dry_run == 1
        assert client.removed == []

    asyncio.run(run())


def test_cleanup_propagates_transport_failure_from_status_check(tmp_path: Path) -> None:
    async def run() -> None:
        client = FakeOfflineClient()
        collector = RawRecordingCollector(client, RawRecordingStore(tmp_path / "raw"))  # type: ignore[arg-type]
        await collector.collect("AA:BB:CC:DD:EE:FF", record_types={"ACC"})

        with pytest.raises(BleConnectionError, match="link lost"):
            await collector.cleanup(
                "AA:BB:CC:DD:EE:FF",
                record_types={"ACC"},
                control_client=FakeControlClient(error=BleConnectionError("link lost")),  # type: ignore[arg-type]
            )

    asyncio.run(run())
