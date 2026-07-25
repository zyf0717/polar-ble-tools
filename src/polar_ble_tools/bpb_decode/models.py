from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SUPPORTED_STATUS = "decoded"
UNSUPPORTED_STATUS = "unsupported"
FAILED_STATUS = "failed"


class BpbManifestError(RuntimeError):
    """Raised when a BPB fetch manifest cannot be read safely."""


@dataclass(frozen=True)
class BpbDecodeResult:
    status: str
    local_path: str
    device_path: str | None
    file_size: int | None
    sha256: str | None
    schema_id: str | None
    message_type: str | None
    data: dict[str, Any] | None
    reason: str | None = None
    error: str | None = None

    def to_jsonable(self) -> dict[str, object]:
        return {
            "data": self.data,
            "device_path": self.device_path,
            "error": self.error,
            "file_size": self.file_size,
            "local_path": self.local_path,
            "message_type": self.message_type,
            "reason": self.reason,
            "schema_id": self.schema_id,
            "sha256": self.sha256,
            "status": self.status,
        }


@dataclass(frozen=True)
class BpbManifestDecodeResult:
    manifest_path: str
    output_dir: str
    listed: int
    decoded: int
    unsupported: int
    failed: int
    results: list[BpbDecodeResult]

    @property
    def ok(self) -> bool:
        return self.failed == 0

    def to_jsonable(self) -> dict[str, object]:
        return {
            "decoded": self.decoded,
            "failed": self.failed,
            "listed": self.listed,
            "manifest_path": self.manifest_path,
            "output_dir": self.output_dir,
            "results": [result.to_jsonable() for result in self.results],
            "unsupported": self.unsupported,
        }
