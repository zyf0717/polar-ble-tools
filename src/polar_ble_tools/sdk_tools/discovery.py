from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class ProtoDiscoveryError(RuntimeError):
    """Raised when a protobuf source tree has no unambiguous import layout."""


@dataclass(frozen=True)
class ProtoInput:
    root: Path
    relative_path: str


@dataclass(frozen=True)
class ProtoLayout:
    sdk_path: Path
    roots: tuple[Path, ...]
    files: tuple[ProtoInput, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "sdk_path": str(self.sdk_path),
            "proto_roots": [str(root) for root in self.roots],
            "files": [item.relative_path for item in self.files],
        }


def _candidate_roots(sdk_path: Path, files: list[Path]) -> tuple[Path, ...]:
    named_proto_roots = {
        ancestor
        for proto_file in files
        for ancestor in proto_file.parents
        if ancestor.name == "proto" and (sdk_path == ancestor or sdk_path in ancestor.parents)
    }
    if named_proto_roots:
        return tuple(sorted(named_proto_roots))
    return tuple(sorted({proto_file.parent for proto_file in files}))


def discover_proto_layout(sdk_path: Path) -> ProtoLayout:
    """Locate protobuf roots without hard-coding an SDK-specific path."""
    sdk_path = sdk_path.expanduser().resolve()
    if not sdk_path.is_dir():
        raise ProtoDiscoveryError(f"SDK source path does not exist: {sdk_path}")
    source_files = sorted(path for path in sdk_path.rglob("*.proto") if path.is_file())
    if not source_files:
        raise ProtoDiscoveryError(f"No .proto files found below {sdk_path}.")

    roots = _candidate_roots(sdk_path, source_files)
    inputs: list[ProtoInput] = []
    seen: dict[str, Path] = {}
    for source_file in source_files:
        matching_roots = [root for root in roots if source_file.is_relative_to(root)]
        if not matching_roots:
            raise ProtoDiscoveryError(f"No protobuf root resolves {source_file}.")
        root = max(matching_roots, key=lambda candidate: len(candidate.parts))
        relative_path = source_file.relative_to(root).as_posix()
        prior = seen.get(relative_path)
        if prior is not None and prior != source_file:
            raise ProtoDiscoveryError(
                "Ambiguous protobuf layout: "
                f"{relative_path} resolves to both {prior} and {source_file}."
            )
        seen[relative_path] = source_file
        inputs.append(ProtoInput(root=root, relative_path=relative_path))
    return ProtoLayout(sdk_path=sdk_path, roots=roots, files=tuple(inputs))
