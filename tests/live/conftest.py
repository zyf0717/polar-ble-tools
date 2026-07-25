"""Release-gate semantics for opt-in protected hardware tests."""

from __future__ import annotations

import os

import pytest

RELEASE_GATE_ENV = "POLAR_BLE_RELEASE_GATE"
REQUIRED_TESTS = frozenset(
    {
        "test_live_pair_ftu_record_and_fetch_raw",
        "test_live_managed_reconnect_and_pmd_probe",
        "test_live_passive_fetch_and_hash_store",
        "test_live_cleanup_dry_run_never_deletes_device_data",
    }
)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[object]):
    """Turn required release-gate skips into explicit failures."""
    outcome = yield
    report = outcome.get_result()
    if (
        os.environ.get(RELEASE_GATE_ENV) == "1"
        and item.name in REQUIRED_TESTS
        and report.skipped
        and report.when in {"setup", "call"}
    ):
        report.outcome = "failed"
        report.longrepr = (
            "Required 0.1.0 live release-gate test skipped. Configure the protected "
            "primary MAC, authorized inventory, FTU profile, schema cache, and passive data."
        )
