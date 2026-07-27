from __future__ import annotations

import re
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
from pathlib import PurePosixPath

from polar_ble_tools.polar.pftp import PftpClient, PftpResponseError

NO_SUCH_FILE_OR_DIRECTORY = 103
AUTOS_DIRECTORY = "/U/0/AUTOS/"


class PassiveDomain(str, Enum):
    ACTIVITY_SAMPLES = "activity_samples"
    DAILY_SUMMARY = "daily_summary"
    AUTOS = "autos"
    SLEEP = "sleep"
    NIGHTLY_RECHARGE = "nightly_recharge"
    SKIN_TEMPERATURE = "skin_temperature"


PASSIVE_DOMAIN_ORDER = tuple(PassiveDomain)
PASSIVE_DOMAIN_ALIASES = {
    "activity": PassiveDomain.ACTIVITY_SAMPLES,
    "activity_samples": PassiveDomain.ACTIVITY_SAMPLES,
    "daily": PassiveDomain.DAILY_SUMMARY,
    "daily_summary": PassiveDomain.DAILY_SUMMARY,
    "autos": PassiveDomain.AUTOS,
    "auto_samples": PassiveDomain.AUTOS,
    "sleep": PassiveDomain.SLEEP,
    "nightly": PassiveDomain.NIGHTLY_RECHARGE,
    "nightly_recharge": PassiveDomain.NIGHTLY_RECHARGE,
    "skin": PassiveDomain.SKIN_TEMPERATURE,
    "skin_temperature": PassiveDomain.SKIN_TEMPERATURE,
}


@dataclass(frozen=True)
class PassiveFileEntry:
    domain: PassiveDomain
    path: str
    size: int
    logical_date: date | None = None

    @property
    def filename(self) -> str:
        return PurePosixPath(self.path).name


@dataclass(frozen=True)
class PassiveFileListing:
    entries: list[PassiveFileEntry]
    missing: list[str]


class PassiveDataClient:
    """Raw passive PFTP access. Schema decoding intentionally lives elsewhere."""

    def __init__(self, pftp_client: PftpClient) -> None:
        self.pftp_client = pftp_client

    @asynccontextmanager
    async def sync_session(self):
        """Own one complete PFTP passive-data synchronization lifecycle."""
        await self.pftp_client.send_initialization_and_start_sync_notifications()
        completed = False
        body_failed = False
        try:
            yield self
            completed = True
        except BaseException:
            body_failed = True
            raise
        finally:
            try:
                await self.pftp_client.send_terminate_and_stop_sync_notifications(
                    completed=completed
                )
            except BaseException:
                if not body_failed:
                    raise

    async def list_files(
        self, domains: tuple[PassiveDomain, ...], *, from_date: date, to_date: date
    ) -> PassiveFileListing:
        if from_date > to_date:
            raise ValueError("from_date must be before or equal to to_date.")
        entries: list[PassiveFileEntry] = []
        missing: list[str] = []
        for domain in domains:
            if domain == PassiveDomain.AUTOS:
                directory = AUTOS_DIRECTORY
                pattern = re.compile(r"AUTOS\d{3}\.BPB", re.IGNORECASE)
                dates = (None,)
            else:
                dates = tuple(iter_dates(from_date, to_date))
            for logical_date in dates:
                directory, expected = _location(domain, logical_date)
                try:
                    listed = await self.pftp_client.list_directory(directory)
                except PftpResponseError as exc:
                    if exc.error_code == NO_SUCH_FILE_OR_DIRECTORY:
                        missing.append(expected or directory)
                        continue
                    raise
                for item in listed:
                    if item.name.upper().endswith(".BPB") and (
                        domain != PassiveDomain.AUTOS or pattern.fullmatch(item.name)
                    ):
                        if (
                            expected is None
                            or item.name.upper() == PurePosixPath(expected).name.upper()
                            or domain == PassiveDomain.ACTIVITY_SAMPLES
                            or domain == PassiveDomain.AUTOS
                        ):
                            entries.append(
                                PassiveFileEntry(
                                    domain,
                                    f"{directory.rstrip('/')}/{item.name}",
                                    item.size,
                                    logical_date,
                                )
                            )
                if expected and not any(
                    entry.path.upper() == expected.upper() for entry in entries
                ):
                    missing.append(expected)
        return PassiveFileListing(
            sorted(entries, key=lambda item: (item.domain.value, item.path)), sorted(set(missing))
        )

    async def fetch_raw_file(self, entry: PassiveFileEntry) -> bytes:
        return await self.pftp_client.get_file(entry.path)

    async def remove_file(self, entry: PassiveFileEntry) -> None:
        await self.pftp_client.remove_file(entry.path)


def normalize_passive_domain(raw: PassiveDomain | str) -> PassiveDomain:
    if isinstance(raw, PassiveDomain):
        return raw
    key = raw.strip().lower().replace("-", "_")
    return PASSIVE_DOMAIN_ALIASES.get(key, PassiveDomain(key))


def iter_dates(from_date: date, to_date: date):
    current = from_date
    while current <= to_date:
        yield current
        current += timedelta(days=1)


def _location(domain: PassiveDomain, logical_date: date | None) -> tuple[str, str | None]:
    if domain == PassiveDomain.AUTOS:
        return AUTOS_DIRECTORY, None
    assert logical_date is not None
    base = f"/U/0/{logical_date:%Y%m%d}/"
    mapping = {
        PassiveDomain.DAILY_SUMMARY: ("DSUM", "DSUM.BPB"),
        PassiveDomain.SLEEP: ("SLEEP", "SLEEPRES.BPB"),
        PassiveDomain.NIGHTLY_RECHARGE: ("NR", "NR.BPB"),
        PassiveDomain.SKIN_TEMPERATURE: ("SKINTEMP", "TEMPCONT.BPB"),
    }
    if domain == PassiveDomain.ACTIVITY_SAMPLES:
        return base + "ACT/", None
    directory, filename = mapping[domain]
    return base + directory + "/", base + directory + "/" + filename
