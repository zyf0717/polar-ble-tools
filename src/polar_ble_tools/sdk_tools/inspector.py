from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from google.protobuf.descriptor_pb2 import (
    DescriptorProto,
    EnumDescriptorProto,
    FieldDescriptorProto,
    FileDescriptorProto,
    FileDescriptorSet,
)


def _full_name(package: str, parents: tuple[str, ...], name: str) -> str:
    return ".".join(part for part in (package, *parents, name) if part)


def _messages(
    descriptor: FileDescriptorProto,
    messages: tuple[DescriptorProto, ...] | list[DescriptorProto],
    parents: tuple[str, ...] = (),
) -> Iterator[dict[str, object]]:
    for message in messages:
        yield {
            "name": _full_name(descriptor.package, parents, message.name),
            "file": descriptor.name,
            "fields": [
                {
                    "name": field.name,
                    "number": field.number,
                    "label": FieldDescriptorProto.Label.Name(field.label),
                    "type": FieldDescriptorProto.Type.Name(field.type),
                    "type_name": field.type_name or None,
                }
                for field in message.field
            ],
        }
        yield from _messages(descriptor, message.nested_type, (*parents, message.name))


def _enums(
    descriptor: FileDescriptorProto,
    enums: tuple[EnumDescriptorProto, ...] | list[EnumDescriptorProto],
    parents: tuple[str, ...] = (),
) -> Iterator[dict[str, object]]:
    for enum in enums:
        yield {
            "name": _full_name(descriptor.package, parents, enum.name),
            "file": descriptor.name,
            "values": [{"name": value.name, "number": value.number} for value in enum.value],
        }


def inspect_descriptor_set(descriptor_set: FileDescriptorSet) -> dict[str, object]:
    """Return a deterministic, JSON-serialisable protobuf inventory."""
    files: list[dict[str, object]] = []
    messages: list[dict[str, object]] = []
    enums: list[dict[str, object]] = []
    dependencies: dict[str, list[str]] = {}
    for descriptor in sorted(descriptor_set.file, key=lambda value: value.name):
        imports = list(descriptor.dependency)
        public_imports = [descriptor.dependency[index] for index in descriptor.public_dependency]
        files.append(
            {
                "name": descriptor.name,
                "package": descriptor.package,
                "imports": imports,
                "public_imports": public_imports,
            }
        )
        dependencies[descriptor.name] = imports
        messages.extend(_messages(descriptor, descriptor.message_type))
        enums.extend(_enums(descriptor, descriptor.enum_type))
        for message in descriptor.message_type:
            enums.extend(_enums(descriptor, message.enum_type, (message.name,)))
    return {
        "files": files,
        "messages": sorted(messages, key=lambda value: str(value["name"])),
        "enums": sorted(enums, key=lambda value: str(value["name"])),
        "dependencies": dependencies,
    }


def inspect_descriptor_file(path: Path) -> dict[str, object]:
    descriptor_set = FileDescriptorSet()
    descriptor_set.ParseFromString(path.read_bytes())
    return inspect_descriptor_set(descriptor_set)
