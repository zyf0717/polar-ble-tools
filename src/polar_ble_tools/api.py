"""High-level Python entry points matching operational CLI workflows."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from polar_ble_tools.ble.transport import BleTransport
    from polar_ble_tools.device import PolarDeviceTarget
    from polar_ble_tools.polar.setup import (
        FtuProfile,
        PhysicalConfiguration,
        UserDeviceSettings,
        UserDeviceSettingsPatch,
    )
    from polar_ble_tools.rec import DecoderStatus
    from polar_ble_tools.schemas.cache import SdkCache
    from polar_ble_tools.sdk_tools.downloader import SdkStatus


@dataclass(frozen=True)
class DoctorSchemaStatus:
    ready: bool
    active_commit: str | None = None
    path: Path | None = None
    error: str | None = None
    remediation: str | None = None

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["path"] = str(self.path) if self.path is not None else None
        return result


@dataclass(frozen=True)
class DoctorReport:
    sdk: SdkStatus
    schemas: DoctorSchemaStatus
    decoder: DecoderStatus

    def to_dict(self) -> dict[str, object]:
        return {
            "core": {"ready": True},
            "sdk": {
                "active_commit": self.sdk.active_commit,
                "installed_commits": list(self.sdk.installed_commits),
            },
            "schemas": self.schemas.to_dict(),
            "decoder": asdict(self.decoder),
        }


@dataclass(frozen=True)
class FtuApplyResult:
    ftu_applied: bool
    settings_updated: bool


def doctor(*, cache: SdkCache | None = None) -> DoctorReport:
    """Return core, SDK-schema, and REC-decoder readiness without mutation."""
    from polar_ble_tools.rec import decoder_status
    from polar_ble_tools.schemas.cache import SdkCache
    from polar_ble_tools.sdk_tools.downloader import SdkDownloadError, sdk_status
    from polar_ble_tools.sdk_tools.verifier import (
        SchemaVerificationError,
        verify_active_schemas,
    )

    cache = cache or SdkCache.default()
    sdk = sdk_status(cache=cache)
    if sdk.active_commit is None:
        schemas = DoctorSchemaStatus(
            ready=False, remediation="polar-ble sdk install --accept-license"
        )
    else:
        try:
            schema_root = verify_active_schemas(cache=cache)
        except (SdkDownloadError, SchemaVerificationError, OSError, ValueError) as exc:
            schemas = DoctorSchemaStatus(
                ready=False,
                active_commit=sdk.active_commit,
                error=str(exc),
                remediation="polar-ble sdk verify",
            )
        else:
            schemas = DoctorSchemaStatus(
                ready=True, active_commit=sdk.active_commit, path=schema_root
            )
    return DoctorReport(sdk=sdk, schemas=schemas, decoder=decoder_status(cache=cache))


def _device(target: PolarDeviceTarget | str, transport_factory: Callable[[], BleTransport] | None):
    from polar_ble_tools.device import open_polar_device

    return open_polar_device(target, transport_factory=transport_factory)


async def apply_ftu(
    target: PolarDeviceTarget | str,
    profile: FtuProfile,
    *,
    transport_factory: Callable[[], BleTransport] | None = None,
) -> FtuApplyResult:
    """Apply a validated FTU profile and its optional initial settings patch."""
    async with _device(target, transport_factory) as device:
        setup = device.services.setup
        await setup.do_first_time_use(profile)
        patch = profile.user_device_settings
        if patch is not None and patch.has_changes:
            await setup.set_user_device_settings(patch)
            return FtuApplyResult(ftu_applied=True, settings_updated=True)
    return FtuApplyResult(ftu_applied=True, settings_updated=False)


async def ftu_status(
    target: PolarDeviceTarget | str, *, transport_factory: Callable[[], BleTransport] | None = None
) -> bool:
    async with _device(target, transport_factory) as device:
        return await device.services.setup.is_ftu_done()


async def physical_configuration(
    target: PolarDeviceTarget | str, *, transport_factory: Callable[[], BleTransport] | None = None
) -> PhysicalConfiguration | None:
    async with _device(target, transport_factory) as device:
        return await device.services.setup.get_physical_configuration()


async def user_device_settings(
    target: PolarDeviceTarget | str, *, transport_factory: Callable[[], BleTransport] | None = None
) -> UserDeviceSettings:
    async with _device(target, transport_factory) as device:
        return await device.services.setup.get_user_device_settings()


async def update_user_device_settings(
    target: PolarDeviceTarget | str,
    patch: UserDeviceSettingsPatch,
    *,
    transport_factory: Callable[[], BleTransport] | None = None,
) -> None:
    async with _device(target, transport_factory) as device:
        await device.services.setup.set_user_device_settings(patch)


async def diagnose_ftu(
    target: PolarDeviceTarget | str, *, transport_factory: Callable[[], BleTransport] | None = None
) -> dict[str, object]:
    async with _device(target, transport_factory) as device:
        return await device.services.setup.diagnose_setup()
