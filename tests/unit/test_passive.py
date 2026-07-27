from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import date
from types import SimpleNamespace

import pytest

import polar_ble_tools.collection as collection
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


def test_passive_sync_session_marks_failure_and_preserves_body_error() -> None:
    class SyncPftp:
        def __init__(self) -> None:
            self.calls: list[object] = []

        async def send_initialization_and_start_sync_notifications(self) -> None:
            self.calls.append("start")

        async def send_terminate_and_stop_sync_notifications(self, *, completed: bool) -> None:
            self.calls.append(("stop", completed))

    async def run() -> None:
        pftp = SyncPftp()
        client = PassiveDataClient(pftp)  # type: ignore[arg-type]
        async with client.sync_session():
            pass
        assert pftp.calls == ["start", ("stop", True)]

        with pytest.raises(RuntimeError, match="body failed"):
            async with client.sync_session():
                raise RuntimeError("body failed")
        assert pftp.calls[-2:] == ["start", ("stop", False)]

    asyncio.run(run())


def test_collection_owns_one_passive_sync_session(monkeypatch) -> None:
    calls: list[str] = []

    class Passive:
        @asynccontextmanager
        async def sync_session(self):
            calls.append("start")
            try:
                yield self
            finally:
                calls.append("stop")

        async def list_files(self, *_args, **_kwargs):
            calls.append("list")
            return "listing"

    device = SimpleNamespace(services=SimpleNamespace(passive=Passive()))

    async def fake_run(_self, _target, workflow):
        return await workflow(device)

    monkeypatch.setattr(collection.DeviceWorkflowRunner, "run", fake_run)

    result = asyncio.run(
        collection.list_passive_files(
            "AA:BB:CC:DD:EE:FF",
            domains=(PassiveDomain.DAILY_SUMMARY,),
            from_date=date(2026, 6, 25),
            to_date=date(2026, 6, 25),
        )
    )

    assert result == "listing"
    assert calls == ["start", "list", "stop"]
