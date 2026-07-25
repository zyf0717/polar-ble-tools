from __future__ import annotations

import argparse

from polar_ble_tools.commands.common import print_json
from polar_ble_tools.sdk_tools.downloader import SdkDownloadError, sdk_status
from polar_ble_tools.sdk_tools.verifier import (
    SchemaVerificationError,
    verify_active_schemas,
)


def doctor_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="polar-ble doctor",
        description="Report core and optional local-schema readiness.",
    )
    parser.parse_args(argv)
    status = sdk_status()
    schema: dict[str, object]
    if status.active_commit is None:
        schema = {
            "ready": False,
            "remediation": "polar-ble sdk install --accept-license",
        }
    else:
        try:
            schema_root = verify_active_schemas()
        except (SdkDownloadError, SchemaVerificationError, OSError, ValueError) as exc:
            schema = {
                "ready": False,
                "active_commit": status.active_commit,
                "error": str(exc),
                "remediation": "polar-ble sdk verify",
            }
        else:
            schema = {
                "ready": True,
                "active_commit": status.active_commit,
                "path": str(schema_root),
            }
    print_json(
        {
            "core": {"ready": True},
            "sdk": {
                "active_commit": status.active_commit,
                "installed_commits": list(status.installed_commits),
            },
            "schemas": schema,
        }
    )
    return 0
