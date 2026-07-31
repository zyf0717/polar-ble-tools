"""Opt-in live release-matrix checks that avoid destructive device operations.

The primary probe requires an ignored ``test_devices.yaml`` authorization and
stores only hashes and raw passive data beneath ``.local/``.  It never deletes
device data.  A second device is optional and exercises concurrent sessions
only when explicitly configured.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import TypeVar

import pytest

from polar_ble_tools.bpb_decode import SUPPORTED_STATUS, decode_bpb_file
from polar_ble_tools.collection import cleanup_raw_recordings
from polar_ble_tools.device import open_polar_device
from polar_ble_tools.inventory import InventoryError, load_allowed_identifiers
from polar_ble_tools.passive_data.storage import PassiveFileStore
from polar_ble_tools.polar.passive import PassiveDomain

LIVE_MATRIX_ENV = "POLAR_BLE_LIVE_MATRIX"
LIVE_MAC_ENV = "POLAR_BLE_LIVE_MAC"
LIVE_SECONDARY_MAC_ENV = "POLAR_BLE_LIVE_SECONDARY_MAC"
LIVE_RAW_ROOT_ENV = "POLAR_BLE_LIVE_RAW_ROOT"
LIVE_MATRIX_ROOT_ENV = "POLAR_BLE_LIVE_MATRIX_ROOT"
TEST_DEVICES_FILE = Path("test_devices.yaml")
DEFAULT_RAW_ROOT = Path(".local/polar-ble-live-raw")
DEFAULT_MATRIX_ROOT = Path(".local/polar-ble-live-matrix")
PASSIVE_LOOKBACK_DAYS = 14
LIVE_OPERATION_TIMEOUT_SECONDS = 60.0
RECONNECT_ATTEMPTS = 3
RECONNECT_SEQUENCE_TIMEOUT_SECONDS = 30.0
RECONNECT_RETRY_DELAY_SECONDS = 2.0
T = TypeVar("T")


@dataclass(frozen=True)
class LiveMatrixConfig:
    mac_address: str
    raw_root: Path
    matrix_root: Path


def test_live_managed_reconnect_and_pmd_probe() -> None:
    config = _load_config()

    result = asyncio.run(
        _with_timeout(
            _probe_reconnect_and_pmd(config.mac_address),
            "managed reconnect/PMD probe",
        )
    )
    assert result["available_types"]
    assert result["first_status_types"] == result["second_status_types"]
    print(
        "live_matrix_reconnect_pmd=passed "
        f"available_types={len(result['available_types'])} "
        f"recordings={result['recording_count']}"
    )


def test_live_passive_fetch_and_hash_store() -> None:
    config = _load_config()
    result = asyncio.run(_with_timeout(_fetch_one_passive_file(config), "passive probe"))

    assert result["fetched_size"] == result["device_size"]
    assert result["manifest_verified"] is True
    assert result["manifest_contains_file"] is True
    assert result["bpb_decoded"] is True
    print(
        "live_matrix_passive=passed "
        f"domain={result['domain']} fetched_bytes={result['fetched_size']}"
    )


def test_live_cleanup_dry_run_never_deletes_device_data() -> None:
    config = _load_config()
    result = asyncio.run(
        _with_timeout(
            cleanup_raw_recordings(
                config.mac_address,
                root=config.raw_root,
                record_types={"ACC"},
                dry_run=True,
            ),
            "cleanup dry-run probe",
        )
    )

    assert result.deleted == 0
    assert all(record.status != "deleted" for record in result.records)
    print(
        "live_matrix_cleanup_dry_run=passed "
        f"selected={result.selected} dry_run={result.dry_run} blocked={result.blocked}"
    )


def test_live_two_device_concurrent_probe() -> None:
    primary = _load_config()
    secondary = os.environ.get(LIVE_SECONDARY_MAC_ENV)
    if not secondary:
        pytest.skip(f"{LIVE_SECONDARY_MAC_ENV} is required for the multi-device probe.")
    secondary = _load_authorized_mac(secondary)
    if secondary == primary.mac_address:
        raise AssertionError(f"{LIVE_SECONDARY_MAC_ENV} must differ from {LIVE_MAC_ENV}.")

    first, second = asyncio.run(
        _with_timeout(
            _probe_two_devices(primary.mac_address, secondary),
            "two-device probe",
        )
    )
    assert first and second
    print("live_matrix_multi_device=passed devices=2")


def _load_config() -> LiveMatrixConfig:
    if os.environ.get(LIVE_MATRIX_ENV) != "1":
        pytest.skip(f"{LIVE_MATRIX_ENV}=1 is required.")
    mac_address = os.environ.get(LIVE_MAC_ENV)
    if not mac_address:
        pytest.skip(f"{LIVE_MAC_ENV} is required to select one device.")
    return LiveMatrixConfig(
        mac_address=_load_authorized_mac(mac_address),
        raw_root=_local_root(LIVE_RAW_ROOT_ENV, DEFAULT_RAW_ROOT),
        matrix_root=_local_root(LIVE_MATRIX_ROOT_ENV, DEFAULT_MATRIX_ROOT),
    )


def _load_authorized_mac(mac_address: str) -> str:
    if not TEST_DEVICES_FILE.is_file():
        raise AssertionError(
            f"Live matrix requires a local authorized inventory: {TEST_DEVICES_FILE}"
        )
    try:
        allowed_devices = load_allowed_identifiers(TEST_DEVICES_FILE)
    except InventoryError as exc:
        raise AssertionError(f"Invalid live test device inventory: {exc}") from exc
    normalized = mac_address.upper()
    if normalized not in allowed_devices:
        raise AssertionError(
            f"Live matrix target {normalized} is not authorized in {TEST_DEVICES_FILE}."
        )
    return normalized


def _local_root(environment_name: str, default: Path) -> Path:
    root = Path(os.environ.get(environment_name, default))
    local_root = (Path.cwd() / ".local").resolve()
    if not root.resolve().is_relative_to(local_root):
        raise AssertionError(f"{environment_name} must remain beneath {local_root}.")
    return root


async def _probe_reconnect_and_pmd(mac_address: str) -> dict[str, object]:
    last_error: Exception | None = None
    for _attempt in range(RECONNECT_ATTEMPTS):
        try:
            return await asyncio.wait_for(
                _probe_reconnect_and_pmd_once(mac_address),
                timeout=RECONNECT_SEQUENCE_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            last_error = exc
            await asyncio.sleep(RECONNECT_RETRY_DELAY_SECONDS)
    raise AssertionError(
        f"Managed reconnect did not stabilize after {RECONNECT_ATTEMPTS} attempts."
    ) from last_error


async def _probe_reconnect_and_pmd_once(mac_address: str) -> dict[str, object]:
    async with open_polar_device(mac_address) as first:
        available = await first.services.offline_control.get_available_recording_types()
        first_status = await first.services.offline_control.get_recording_status()
        recordings = await first.services.offline.list_recording_files()

    async with open_polar_device(mac_address) as second:
        second_status = await second.services.offline_control.get_recording_status()

    return {
        "available_types": sorted(item.value for item in available),
        "first_status_types": sorted(item.value for item in first_status),
        "recording_count": len(recordings),
        "second_status_types": sorted(item.value for item in second_status),
    }


async def _fetch_one_passive_file(config: LiveMatrixConfig) -> dict[str, object]:
    today = date.today()
    async with open_polar_device(config.mac_address) as device:
        listing = await device.services.passive.list_files(
            (PassiveDomain.DAILY_SUMMARY,),
            from_date=today - timedelta(days=PASSIVE_LOOKBACK_DAYS),
            to_date=today,
        )
        if not listing.entries:
            pytest.skip("No daily-summary BPB file exists in the passive lookback window.")
        entry = max(listing.entries, key=lambda item: item.path)
        payload = await device.services.passive.fetch_raw_file(entry)

    store = PassiveFileStore(config.matrix_root / "passive")
    manifest = store.persist_file(
        config.mac_address,
        domain=entry.domain.value,
        device_path=entry.path,
        device_size=entry.size,
        payload=payload,
        logical_date=entry.logical_date.isoformat() if entry.logical_date else None,
    )
    manifest_entries = store.read_manifest(config.mac_address)
    decoded = decode_bpb_file(
        store.resolve_local_path(manifest.local_path),
        device_path=entry.path,
    )
    return {
        "bpb_decoded": decoded.status == SUPPORTED_STATUS,
        "device_size": entry.size,
        "domain": entry.domain.value,
        "fetched_size": len(payload),
        "manifest_verified": store.verify_existing_file(
            config.mac_address,
            device_path=entry.path,
            device_size=entry.size,
        )
        == manifest,
        "manifest_contains_file": manifest in manifest_entries,
    }


async def _read_only_device_probe(mac_address: str) -> bool:
    async with open_polar_device(mac_address) as device:
        return bool(await device.services.offline_control.get_available_recording_types())


async def _probe_two_devices(first: str, second: str) -> tuple[bool, bool]:
    first_result, second_result = await asyncio.gather(
        _read_only_device_probe(first),
        _read_only_device_probe(second),
    )
    return first_result, second_result


async def _with_timeout(awaitable: Awaitable[T], operation: str) -> T:
    try:
        return await asyncio.wait_for(awaitable, timeout=LIVE_OPERATION_TIMEOUT_SECONDS)
    except TimeoutError as exc:
        raise AssertionError(
            f"Live {operation} exceeded {LIVE_OPERATION_TIMEOUT_SECONDS:.0f} seconds. "
            "Inspect protected runner Bluetooth logs before retrying."
        ) from exc
