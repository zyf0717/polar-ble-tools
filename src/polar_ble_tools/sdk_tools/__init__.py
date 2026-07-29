"""Explicit commands for acquiring and validating local SDK inputs."""

from polar_ble_tools.sdk_tools.downloader import (
    OFFICIAL_SDK_URL,
    SdkDownloadError,
    SdkInstallResult,
    SdkStatus,
    active_sdk_source,
    install_sdk,
    remove_all_sdk_cache,
    remove_sdk,
    sdk_status,
)
from polar_ble_tools.sdk_tools.inspection import SdkInspectionResult, inspect_active_sdk
from polar_ble_tools.sdk_tools.removal import (
    RemovalArtifactStatus,
    SdkRemovalError,
    SdkRemovalRecord,
    SdkRemovalResult,
    remove_sdk_artifacts,
)
from polar_ble_tools.sdk_tools.verifier import (
    SchemaProvenance,
    SchemaStatus,
    SchemaVerificationError,
    activate_schemas,
    schema_provenance,
    schema_status,
    verify_schemas,
)

__all__ = [
    "OFFICIAL_SDK_URL",
    "SdkDownloadError",
    "SdkInstallResult",
    "SdkRemovalError",
    "SdkRemovalRecord",
    "SdkRemovalResult",
    "SdkStatus",
    "SchemaProvenance",
    "SchemaStatus",
    "SchemaVerificationError",
    "SdkInspectionResult",
    "RemovalArtifactStatus",
    "active_sdk_source",
    "activate_schemas",
    "install_sdk",
    "inspect_active_sdk",
    "remove_all_sdk_cache",
    "remove_sdk",
    "remove_sdk_artifacts",
    "schema_provenance",
    "schema_status",
    "sdk_status",
    "verify_schemas",
]
