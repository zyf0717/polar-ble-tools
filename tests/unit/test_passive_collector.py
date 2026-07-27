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


def test_delete_after_collect_retains_latest_date_and_audits_deletion(tmp_path: Path) -> None:
    class Client:
        def __init__(self) -> None:
            self.entries = [
                PassiveFileEntry(
                    PassiveDomain.DAILY_SUMMARY,
                    "/U/0/20260624/DSUM/DSUM.BPB",
                    3,
                    date(2026, 6, 24),
                ),
                PassiveFileEntry(
                    PassiveDomain.DAILY_SUMMARY,
                    "/U/0/20260625/DSUM/DSUM.BPB",
                    3,
                    date(2026, 6, 25),
                ),
            ]
            self.removed: list[str] = []

        async def list_files(self, *_args, **_kwargs):
            return PassiveFileListing(self.entries, [])

        async def fetch_raw_file(self, _entry):
            return b"raw"

        async def remove_file(self, entry):
            self.removed.append(entry.path)

    async def run() -> None:
        client = Client()
        store = PassiveFileStore(tmp_path)
        result = await PassiveFileCollector(client, store).collect(  # type: ignore[arg-type]
            "AA:BB:CC:DD:EE:FF",
            (PassiveDomain.DAILY_SUMMARY,),
            from_date=date(2026, 6, 24),
            to_date=date(2026, 6, 25),
            delete_after_collect=True,
        )
        assert client.removed == ["/U/0/20260624/DSUM/DSUM.BPB"]
        assert result.deleted == 1
        assert result.records[1].delete_status is None
        assert '"status":"deleted"' in store.deletion_audit_path("AA:BB:CC:DD:EE:FF").read_text()

    asyncio.run(run())


def test_cleanup_dry_run_is_local_and_destructive_cleanup_removes_verified_file(
    tmp_path: Path,
) -> None:
    class Client:
        removed: list[str] = []

        async def remove_file(self, entry):
            self.removed.append(entry.path)

    async def run() -> None:
        store = PassiveFileStore(tmp_path)
        store.persist_file(
            "AA:BB:CC:DD:EE:FF",
            domain="daily_summary",
            device_path="/U/0/20260624/DSUM/DSUM.BPB",
            device_size=3,
            payload=b"raw",
            logical_date="2026-06-24",
        )
        dry = await PassiveFileCollector(None, store).cleanup(  # type: ignore[arg-type]
            "AA:BB:CC:DD:EE:FF",
            domain=PassiveDomain.DAILY_SUMMARY,
            delete_through=date(2026, 6, 24),
            dry_run=True,
        )
        client = Client()
        deleted = await PassiveFileCollector(client, store).cleanup(  # type: ignore[arg-type]
            "AA:BB:CC:DD:EE:FF",
            domain=PassiveDomain.DAILY_SUMMARY,
            delete_through=date(2026, 6, 24),
            dry_run=False,
        )
        assert dry.dry_run == 1
        assert deleted.deleted == 1
        assert client.removed == ["/U/0/20260624/DSUM/DSUM.BPB"]

    asyncio.run(run())
