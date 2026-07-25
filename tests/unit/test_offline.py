from __future__ import annotations

import asyncio

from polar_ble_tools.polar._protobuf import PftpDirectoryEntry
from polar_ble_tools.polar.offline import (
    OfflineRecordingClient,
    OfflineRecordingControlClient,
    base_record_type_for,
    parse_offline_recording_path,
    record_type_matches_filter,
)
from polar_ble_tools.polar.pmd import (
    PmdActiveMeasurement,
    PmdMeasurementType,
    PolarDeviceDataType,
)


class FakePftpClient:
    def __init__(self) -> None:
        self.directories = {
            "/U/": [PftpDirectoryEntry("0", 0)],
            "/U/0/": [
                PftpDirectoryEntry("20260613", 0),
                PftpDirectoryEntry("USERID.BPB", 10),
            ],
            "/U/0/20260613/": [PftpDirectoryEntry("R", 0)],
            "/U/0/20260613/R/": [PftpDirectoryEntry("112233", 0)],
            "/U/0/20260613/R/112233/": [
                PftpDirectoryEntry("ACC0.REC", 8),
                PftpDirectoryEntry("ACC1.REC", 9),
                PftpDirectoryEntry("NOTE.TXT", 1),
            ],
        }
        self.removed: list[str] = []

    async def list_directory(self, path: str) -> list[PftpDirectoryEntry]:
        return list(self.directories.get(path, []))

    async def get_file(self, path: str) -> bytes:
        assert path == "/U/0/20260613/R/112233/ACC0.REC"
        return b"raw-record"

    async def remove_file(self, path: str) -> None:
        self.removed.append(path)
        parent = f"{path.rstrip('/').rsplit('/', 1)[0]}/"
        name = path.rstrip("/").rsplit("/", 1)[1]
        self.directories[parent] = [
            entry for entry in self.directories.get(parent, []) if entry.name != name
        ]
        if path.endswith("/"):
            self.directories.pop(path, None)


def test_offline_client_walks_recordings_and_fetches_payload() -> None:
    async def run() -> None:
        client = OfflineRecordingClient(FakePftpClient())  # type: ignore[arg-type]

        entries = await client.list_recording_files()
        record = await client.fetch_record(entries[0])

        assert [entry.record_type for entry in entries] == ["ACC0", "ACC1"]
        assert record.payload == b"raw-record"

    asyncio.run(run())


def test_offline_client_removes_complete_numbered_family_and_empty_parents() -> None:
    async def run() -> None:
        pftp = FakePftpClient()
        pftp.directories["/U/0/20260613/R/112233/"] = [
            PftpDirectoryEntry("ACC0.REC", 8),
            PftpDirectoryEntry("ACC1.REC", 9),
        ]
        client = OfflineRecordingClient(pftp)  # type: ignore[arg-type]
        entry = parse_offline_recording_path("/U/0/20260613/R/112233/ACC0.REC", size=8)

        result = await client.remove_record(entry)

        assert result.status == "deleted"
        assert result.deleted_paths == [
            "/U/0/20260613/R/112233/ACC0.REC",
            "/U/0/20260613/R/112233/ACC1.REC",
        ]
        assert result.cleaned_directories == [
            "/U/0/20260613/R/112233/",
            "/U/0/20260613/R/",
            "/U/0/20260613/",
        ]
        assert pftp.removed == result.deleted_paths + result.cleaned_directories

    asyncio.run(run())


def test_record_type_aliases_and_numbered_types_are_normalized() -> None:
    assert base_record_type_for("ACC0") == "ACC"
    assert base_record_type_for("MAG0") == "MAGNETOMETER"
    assert record_type_matches_filter("SKINTEMP0", "skin_temperature")
    assert not record_type_matches_filter("ACCA", "ACC")


def test_control_status_maps_only_offline_measurements() -> None:
    class FakePmdClient:
        async def read_measurement_status(self):
            return {
                PmdMeasurementType.ACC: PmdActiveMeasurement.OFFLINE_MEASUREMENT_ACTIVE,
                PmdMeasurementType.PPG: PmdActiveMeasurement.ONLINE_MEASUREMENT_ACTIVE,
            }

    async def run() -> None:
        status = await OfflineRecordingControlClient(  # type: ignore[arg-type]
            FakePmdClient()
        ).get_recording_status()

        assert status == {
            PolarDeviceDataType.ACC: True,
            PolarDeviceDataType.PPG: False,
        }

    asyncio.run(run())
