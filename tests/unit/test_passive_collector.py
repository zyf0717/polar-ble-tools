from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path

from polar_ble_tools.passive_data.collector import PassiveFileCollector
from polar_ble_tools.passive_data.storage import PassiveFileStore
from polar_ble_tools.polar.passive import (
    PassiveDomain,
    PassiveFileEntry,
    PassiveFileListing,
)


class FakePassiveClient:
    def __init__(self) -> None:
        self.fetches = 0
        self.entry = PassiveFileEntry(
            PassiveDomain.DAILY_SUMMARY,
            "/U/0/20260625/DSUM/DSUM.BPB",
            3,
            date(2026, 6, 25),
        )

    async def list_files(self, *args, **kwargs) -> PassiveFileListing:
        return PassiveFileListing([self.entry], ["/U/0/20260626/DSUM/DSUM.BPB"])

    async def fetch_raw_file(self, entry: PassiveFileEntry) -> bytes:
        self.fetches += 1
        return b"raw"


def test_passive_collector_hash_stores_and_skips_verified_files(tmp_path: Path) -> None:
    async def run() -> None:
        client = FakePassiveClient()
        collector = PassiveFileCollector(client, PassiveFileStore(tmp_path))  # type: ignore[arg-type]
        first = await collector.collect(
            "AA:BB:CC:DD:EE:FF",
            (PassiveDomain.DAILY_SUMMARY,),
            from_date=date(2026, 6, 25),
            to_date=date(2026, 6, 25),
        )
        second = await collector.collect(
            "AA:BB:CC:DD:EE:FF",
            (PassiveDomain.DAILY_SUMMARY,),
            from_date=date(2026, 6, 25),
            to_date=date(2026, 6, 25),
        )

        assert (first.fetched, first.skipped, first.failed) == (1, 0, 0)
        assert (second.fetched, second.skipped, second.failed) == (0, 1, 0)
        assert second.missing == ["/U/0/20260626/DSUM/DSUM.BPB"]
        assert client.fetches == 1

    asyncio.run(run())


def test_passive_collector_overwrites_verified_files_when_requested(tmp_path: Path) -> None:
    async def run() -> None:
        client = FakePassiveClient()
        collector = PassiveFileCollector(client, PassiveFileStore(tmp_path))  # type: ignore[arg-type]
        await collector.collect(
            "AA:BB:CC:DD:EE:FF",
            (PassiveDomain.DAILY_SUMMARY,),
            from_date=date(2026, 6, 25),
            to_date=date(2026, 6, 25),
        )
        second = await collector.collect(
            "AA:BB:CC:DD:EE:FF",
            (PassiveDomain.DAILY_SUMMARY,),
            from_date=date(2026, 6, 25),
            to_date=date(2026, 6, 25),
            existing_file_policy="overwrite",
        )

        assert (second.fetched, second.skipped, second.failed) == (1, 0, 0)
        assert client.fetches == 2
        assert len(PassiveFileStore(tmp_path).read_manifest("AA:BB:CC:DD:EE:FF")) == 2

    asyncio.run(run())
