from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from polar_ble_tools.schemas.cache import SdkCache
from polar_ble_tools.sdk_tools.discovery import discover_proto_layout
from polar_ble_tools.sdk_tools.downloader import active_sdk_source
from polar_ble_tools.sdk_tools.inspector import inspect_descriptor_set
from polar_ble_tools.sdk_tools.proto_reader import build_descriptor_set

INSPECTION_FILE = "inspection.json"


@dataclass(frozen=True)
class SdkInspectionResult:
    resolved_commit: str
    report_path: Path
    report: dict[str, object]


def inspect_sdk(
    *,
    resolved_commit: str,
    source: Path,
    cache: SdkCache,
) -> SdkInspectionResult:
    """Inspect the active SDK and persist its machine-readable inventory."""
    commit = resolved_commit
    layout = discover_proto_layout(source)
    with TemporaryDirectory(prefix="polar-ble-inspect-") as temporary:
        descriptor_set = build_descriptor_set(layout, Path(temporary) / "all.desc")
    report = {
        "resolved_commit": commit,
        "layout": layout.to_dict(),
        **inspect_descriptor_set(descriptor_set),
    }
    report_path = cache.sdk_path(commit) / INSPECTION_FILE
    temporary = report_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(report_path)
    return SdkInspectionResult(commit, report_path, report)


def inspect_active_sdk(*, cache: SdkCache | None = None) -> SdkInspectionResult:
    """Inspect the active SDK and persist its machine-readable inventory."""
    cache = cache or SdkCache.default()
    commit, source = active_sdk_source(cache=cache)
    return inspect_sdk(resolved_commit=commit, source=source, cache=cache)
