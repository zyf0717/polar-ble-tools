from __future__ import annotations

from datetime import datetime

from polar_ble_tools.polar.pftp import PftpClient, PftpQuery, PftpResponseError
from polar_ble_tools.polar.setup_payloads import (
    apply_user_device_settings_patch,
    build_local_time_payload,
    build_physical_data_payload,
    build_system_datetime,
    build_system_time_payload,
    build_user_identifier_payload,
    is_user_identifier_present,
    parse_physical_configuration,
    parse_user_device_settings,
    profile_payload_sizes,
)
from polar_ble_tools.polar.setup_types import (
    NO_SUCH_FILE_OR_DIRECTORY,
    PHYSICAL_DATA_PATH,
    USER_DEVICE_SETTINGS_PATH,
    USER_IDENTIFIER_PATH,
    DeviceLocation,
    FtuProfile,
    FtuProfileInput,
    Gender,
    PhysicalConfiguration,
    SetupDeviceResponseError,
    SetupError,
    SetupPartialWriteError,
    SetupStateError,
    SetupUnsupportedError,
    SetupValidationError,
    TypicalDay,
    UserDeviceSettings,
    UserDeviceSettingsPatch,
    VeritySenseFtuProfile,
    load_ftu_profile,
)

# Polar PFTP's explicit unsupported-operation response.  Do not turn timeout,
# transport, malformed-frame, or arbitrary device failures into a time fallback.
SYSTEM_TIME_UNSUPPORTED_ERROR_CODE = 6

__all__ = [
    "DeviceLocation",
    "FtuProfile",
    "FtuProfileInput",
    "Gender",
    "PhysicalConfiguration",
    "PolarSetupClient",
    "SetupDeviceResponseError",
    "SetupError",
    "SetupPartialWriteError",
    "SetupStateError",
    "SetupUnsupportedError",
    "SetupValidationError",
    "TypicalDay",
    "UserDeviceSettings",
    "UserDeviceSettingsPatch",
    "VeritySenseFtuProfile",
    "apply_user_device_settings_patch",
    "build_local_time_payload",
    "build_physical_data_payload",
    "build_system_datetime",
    "build_system_time_payload",
    "build_user_identifier_payload",
    "is_user_identifier_present",
    "load_ftu_profile",
    "parse_physical_configuration",
    "parse_user_device_settings",
    "profile_payload_sizes",
]


class PolarSetupClient:
    def __init__(self, pftp_client: PftpClient) -> None:
        self.pftp_client = pftp_client
        self.used_local_time_fallback = False

    async def do_first_time_use(self, profile: FtuProfile) -> None:
        physical_data = build_physical_data_payload(profile)
        user_identifier = build_user_identifier_payload()
        wrote_physical_data = False
        primary_error: BaseException | None = None
        try:
            await self.pftp_client.send_initialization_and_start_sync_notifications()
            await self.set_local_time(profile.device_time)
            await self.pftp_client.put_file(PHYSICAL_DATA_PATH, physical_data)
            wrote_physical_data = True
            await self.pftp_client.put_file(USER_IDENTIFIER_PATH, user_identifier)
        except Exception as exc:
            primary_error = exc
            if wrote_physical_data:
                raise SetupPartialWriteError(
                    "FTU failed after writing physical data; device state may be partial."
                ) from exc
            raise SetupDeviceResponseError(
                "FTU setup failed before file writes completed."
            ) from exc
        finally:
            try:
                await self.pftp_client.send_terminate_and_stop_sync_notifications()
            except Exception as cleanup_exc:
                if primary_error is None:
                    raise SetupDeviceResponseError(
                        "FTU cleanup notifications failed."
                    ) from cleanup_exc

    async def set_local_time(self, device_time: datetime) -> None:
        self.used_local_time_fallback = False
        try:
            await self.pftp_client.query(
                PftpQuery.SET_SYSTEM_TIME,
                build_system_time_payload(device_time),
            )
        except PftpResponseError as exc:
            if exc.error_code != SYSTEM_TIME_UNSUPPORTED_ERROR_CODE:
                raise
            self.used_local_time_fallback = True
        await self.pftp_client.query(
            PftpQuery.SET_LOCAL_TIME,
            build_local_time_payload(device_time),
        )

    async def is_ftu_done(self) -> bool:
        data = await self.pftp_client.get_file(USER_IDENTIFIER_PATH)
        return is_user_identifier_present(data)

    async def get_physical_configuration(self) -> PhysicalConfiguration | None:
        try:
            data = await self.pftp_client.get_file(PHYSICAL_DATA_PATH)
        except PftpResponseError as exc:
            if exc.error_code == NO_SUCH_FILE_OR_DIRECTORY:
                return None
            raise
        return parse_physical_configuration(data)

    async def get_user_device_settings(self) -> UserDeviceSettings:
        data = await self.pftp_client.get_file(USER_DEVICE_SETTINGS_PATH)
        return parse_user_device_settings(data)

    async def set_user_device_settings(self, patch: UserDeviceSettingsPatch) -> None:
        if not patch.has_changes:
            raise SetupValidationError("at least one user-device setting is required.")
        data = await self.pftp_client.get_file(USER_DEVICE_SETTINGS_PATH)
        updated = apply_user_device_settings_patch(data, patch)
        await self.pftp_client.put_file(USER_DEVICE_SETTINGS_PATH, updated)

    async def diagnose_setup(self) -> dict[str, object]:
        status: dict[str, object] = {
            "pftp_available": True,
            "ftu_done": None,
            "physical_data_present": None,
            "user_device_settings_present": None,
        }
        try:
            status["ftu_done"] = await self.is_ftu_done()
        except Exception as exc:
            status["ftu_done_error"] = type(exc).__name__
        try:
            status["physical_data_present"] = (await self.get_physical_configuration()) is not None
        except Exception as exc:
            status["physical_data_error"] = type(exc).__name__
        try:
            await self.get_user_device_settings()
            status["user_device_settings_present"] = True
        except PftpResponseError as exc:
            if exc.error_code == NO_SUCH_FILE_OR_DIRECTORY:
                status["user_device_settings_present"] = False
            else:
                status["user_device_settings_error"] = type(exc).__name__
        except Exception as exc:
            status["user_device_settings_error"] = type(exc).__name__
        return status
