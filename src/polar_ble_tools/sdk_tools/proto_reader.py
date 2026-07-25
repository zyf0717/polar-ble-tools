from __future__ import annotations

from pathlib import Path

from google.protobuf.descriptor_pb2 import FileDescriptorSet

from polar_ble_tools.sdk_tools.discovery import ProtoLayout


class ProtoReaderError(RuntimeError):
    """Raised when protoc cannot build a complete descriptor set."""


def build_descriptor_set(layout: ProtoLayout, output_path: Path) -> FileDescriptorSet:
    """Build and parse a complete descriptor set using grpcio-tools' protoc."""
    try:
        from grpc_tools import protoc
    except ImportError as exc:
        raise ProtoReaderError(
            "SDK inspection requires the sdk extra. Install with: "
            'pip install "polar-ble-tools[sdk]"'
        ) from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)
    arguments = [
        "grpc_tools.protoc",
        *(f"--proto_path={root}" for root in layout.roots),
        "--include_imports",
        f"--descriptor_set_out={output_path}",
        *(item.relative_path for item in layout.files),
    ]
    result = protoc.main(arguments)
    if result != 0:
        raise ProtoReaderError(f"protoc failed with exit code {result}.")
    descriptor_set = FileDescriptorSet()
    try:
        descriptor_set.ParseFromString(output_path.read_bytes())
    except OSError as exc:
        raise ProtoReaderError(f"Could not read descriptor set {output_path}.") from exc
    return descriptor_set
