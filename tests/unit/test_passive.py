from __future__ import annotations

import asyncio
from datetime import date

from polar_ble_tools.polar._protobuf import PftpDirectoryEntry
from polar_ble_tools.polar.passive import PassiveDataClient, PassiveDomain


class FakePftp:
    def __init__(self) -> None:
        self.directories = {"/U/0/20260625/DSUM/": [PftpDirectoryEntry("DSUM.BPB", 3)]}
        self.files = {"/U/0/20260625/DSUM/DSUM.BPB": b"raw"}

    async def list_directory(self, path):
        return self.directories[path]

    async def get_file(self, path):
        return self.files[path]

    async def remove_file(self, path):
        self.files.pop(path)


def test_passive_listing_and_raw_fetch_do_not_require_schemas() -> None:
    async def run() -> None:
        client = PassiveDataClient(FakePftp())  # type: ignore[arg-type]
        listing = await client.list_files(
            (PassiveDomain.DAILY_SUMMARY,), from_date=date(2026, 6, 25), to_date=date(2026, 6, 25)
        )
        assert [entry.path for entry in listing.entries] == ["/U/0/20260625/DSUM/DSUM.BPB"]
        assert await client.fetch_raw_file(listing.entries[0]) == b"raw"

    asyncio.run(run())
