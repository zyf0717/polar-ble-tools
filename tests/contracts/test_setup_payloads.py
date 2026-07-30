from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256

import pytest

from polar_ble_tools.polar.pftp import PftpQuery
from polar_ble_tools.polar.setup import (
    FtuProfile,
    Gender,
    PolarSetupClient,
    SetupStateError,
    TypicalDay,
    build_local_time_payload,
    build_physical_data_payload,
    build_system_time_payload,
    build_user_identifier_payload,
    parse_local_time_payload,
)

# Digests preserve exact payload bytes for the synthetic input below without
# checking in SDK schema source, generated modules, or personal profile data.
EXPECTED_PAYLOADS = {
    "physical_data": (310, "d3e384d27cc97cb9db28b06656abe2d564657ad3b92f2fb9fb55ebd26a4b74b0"),
    "user_identifier": (35, "9292e8d55aeae2a8a35a8c36fc43aea58f3afa93b88eb74f134d7d67d8a1fed9"),
    "system_time": (21, "b4067aed2e6fb1fed5cc736e6f9295003e3019f5b5e95a8e4cc78dd2817ef599"),
    "local_time": (22, "cd1c1c03bad236e99b5f7ea92faccd3ce333fe1ce7bf7f0736b596b51a228af2"),
}

FIXED_TIME = datetime(2026, 6, 25, 8, 30, 15, 123000, tzinfo=timezone(timedelta(hours=8)))


def _profile() -> FtuProfile:
    return FtuProfile(
        gender=Gender.MALE,
        birth_date=date(1990, 1, 2),
        height_cm=180.5,
        weight_kg=72.25,
        max_heart_rate_bpm=190,
        resting_heart_rate_bpm=55,
        vo2_max=47,
        training_background=30,
        typical_day=TypicalDay.MOSTLY_MOVING,
        sleep_goal_minutes=480,
        device_time=FIXED_TIME,
    )


@pytest.mark.parametrize(
    ("name", "payload"),
    [
        ("physical_data", lambda: build_physical_data_payload(_profile())),
        ("user_identifier", lambda: build_user_identifier_payload(FIXED_TIME)),
        ("system_time", lambda: build_system_time_payload(FIXED_TIME)),
        ("local_time", lambda: build_local_time_payload(FIXED_TIME)),
    ],
)
def test_setup_payload_bytes_match_contract(name: str, payload: object) -> None:
    expected_size, expected_digest = EXPECTED_PAYLOADS[name]
    value = payload()

    assert len(value) == expected_size
    assert sha256(value).hexdigest() == expected_digest


def test_local_time_payload_round_trip_contract() -> None:
    assert parse_local_time_payload(build_local_time_payload(FIXED_TIME)) == FIXED_TIME


def test_local_time_payload_rejects_malformed_response() -> None:
    with pytest.raises(SetupStateError, match="local-time data"):
        parse_local_time_payload(b"\xff")


def test_setup_client_reads_local_time_contract() -> None:
    class FakePftpClient:
        async def query(self, query: PftpQuery, payload: bytes | None = None) -> bytes:
            assert query is PftpQuery.GET_LOCAL_TIME
            assert payload is None
            return build_local_time_payload(FIXED_TIME)

    client = PolarSetupClient(FakePftpClient())

    assert asyncio.run(client.get_local_time()) == FIXED_TIME
