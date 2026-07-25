from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from polar_ble_tools.schemas.cache import SdkCache
from polar_ble_tools.sdk_tools.discovery import (
    ProtoDiscoveryError,
    ProtoLayout,
    discover_proto_layout,
)
from polar_ble_tools.sdk_tools.inspection import inspect_active_sdk
from polar_ble_tools.sdk_tools.inspector import inspect_descriptor_set
from polar_ble_tools.sdk_tools.proto_reader import ProtoReaderError, build_descriptor_set


def _write(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")


def test_discovery_reader_and_inspector_handle_imports_and_nested_types(tmp_path: Path) -> None:
    sdk = tmp_path / "sdk"
    proto_root = sdk / "sources" / "proto"
    _write(
        proto_root / "common.proto",
        """syntax = "proto3";
package sample;
message Common { string id = 1; }
""",
    )
    _write(
        proto_root / "event.proto",
        """syntax = "proto3";
package sample;
import "common.proto";
message Event {
  enum State { UNKNOWN = 0; READY = 1; }
  Common common = 1;
  repeated State states = 2;
}
""",
    )

    layout = discover_proto_layout(sdk)
    descriptor = build_descriptor_set(layout, tmp_path / "selected.desc")
    inspection = inspect_descriptor_set(descriptor)

    assert layout.to_dict()["files"] == ["common.proto", "event.proto"]
    assert inspection["dependencies"] == {"common.proto": [], "event.proto": ["common.proto"]}
    event = next(item for item in inspection["messages"] if item["name"] == "sample.Event")
    assert event["fields"] == [
        {
            "name": "common",
            "number": 1,
            "label": "LABEL_OPTIONAL",
            "type": "TYPE_MESSAGE",
            "type_name": ".sample.Common",
        },
        {
            "name": "states",
            "number": 2,
            "label": "LABEL_REPEATED",
            "type": "TYPE_ENUM",
            "type_name": ".sample.Event.State",
        },
    ]
    assert any(item["name"] == "sample.Event.State" for item in inspection["enums"])


def test_discovery_rejects_duplicate_relative_proto_names(tmp_path: Path) -> None:
    sdk = tmp_path / "sdk"
    _write(sdk / "android" / "proto" / "types.proto", 'syntax = "proto3";')
    _write(sdk / "ios" / "proto" / "types.proto", 'syntax = "proto3";')

    with pytest.raises(ProtoDiscoveryError, match="Ambiguous protobuf layout"):
        discover_proto_layout(sdk)


def test_descriptor_reader_reports_missing_sdk_compiler_extra(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setitem(sys.modules, "grpc_tools", None)
    layout = ProtoLayout(sdk_path=tmp_path, roots=(), files=())

    with pytest.raises(ProtoReaderError, match=r'pip install "polar-ble-tools\[sdk\]"'):
        build_descriptor_set(layout, tmp_path / "unused.desc")


def test_discovery_handles_multiple_import_roots(tmp_path: Path) -> None:
    sdk = tmp_path / "sdk"
    _write(
        sdk / "shared" / "proto" / "common" / "types.proto",
        'syntax = "proto3"; package sample; message Value { string id = 1; }',
    )
    _write(
        sdk / "android" / "proto" / "api" / "event.proto",
        """syntax = "proto3";
package sample;
import "common/types.proto";
message Event { Value value = 1; }
""",
    )

    layout = discover_proto_layout(sdk)
    descriptor = build_descriptor_set(layout, tmp_path / "selected.desc")
    inspection = inspect_descriptor_set(descriptor)

    assert {root.relative_to(sdk).as_posix() for root in layout.roots} == {
        "android/proto",
        "shared/proto",
    }
    assert inspection["dependencies"] == {
        "api/event.proto": ["common/types.proto"],
        "common/types.proto": [],
    }


def test_active_sdk_inspection_persists_machine_readable_report(tmp_path: Path) -> None:
    cache = SdkCache(tmp_path / "cache")
    commit = "a" * 40
    source = cache.sdk_path(commit) / "source"
    _write(
        source / "proto" / "sample.proto",
        'syntax = "proto3"; package sample; message Value { string id = 1; }',
    )
    (source.parent / "download-manifest.json").write_text("{}", encoding="utf-8")
    cache.active_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    cache.active_manifest_path.write_text(json.dumps({"resolved_commit": commit}), encoding="utf-8")

    result = inspect_active_sdk(cache=cache)

    assert result.resolved_commit == commit
    assert result.report_path == cache.sdk_path(commit) / "inspection.json"
    assert result.report_path.is_file()
    assert result.report["messages"][0]["name"] == "sample.Value"
