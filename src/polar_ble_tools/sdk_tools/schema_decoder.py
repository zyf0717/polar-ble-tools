from __future__ import annotations

from dataclasses import dataclass

from polar_ble_tools.schemas.requirements import SchemaFeatureRequirement, requirements_for


class SchemaResolutionError(RuntimeError):
    """Raised when declared schema requirements cannot be resolved uniquely."""


@dataclass(frozen=True)
class SchemaGenerationPlan:
    features: tuple[str, ...]
    root_files: tuple[str, ...]
    dependency_closure: tuple[str, ...]
    resolved_symbols: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return {
            "features": list(self.features),
            "root_files": list(self.root_files),
            "dependency_closure": list(self.dependency_closure),
            "resolved_symbols": dict(sorted(self.resolved_symbols.items())),
        }


def _module_source(module: str, available_files: set[str]) -> str:
    if not module.endswith("_pb2"):
        raise SchemaResolutionError(f"Generated module name must end in _pb2: {module}")
    source = f"{module.removesuffix('_pb2')}.proto"
    if source not in available_files:
        raise SchemaResolutionError(
            f"Required generated module {module} has no source file {source}."
        )
    return source


def _closure(roots: set[str], dependencies: dict[str, list[str]]) -> tuple[str, ...]:
    ordered: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(name: str) -> None:
        if name in visited:
            return
        if name in visiting:
            raise SchemaResolutionError(f"Protobuf dependency cycle includes {name}.")
        if name not in dependencies:
            raise SchemaResolutionError(f"Descriptor dependency is missing: {name}.")
        visiting.add(name)
        for dependency in sorted(dependencies[name]):
            visit(dependency)
        visiting.remove(name)
        visited.add(name)
        ordered.append(name)

    for root in sorted(roots):
        visit(root)
    return tuple(ordered)


def decode_schema_requirements(
    inspection: dict[str, object],
    *,
    features: tuple[str, ...] = (),
    requirement: SchemaFeatureRequirement | None = None,
) -> SchemaGenerationPlan:
    """Resolve feature requirements into deterministic source-file closure."""
    if requirement is None:
        requirement = requirements_for(*features)
    selected_features = tuple(sorted(features or tuple(requirement and ())))
    raw_files = inspection.get("files")
    raw_messages = inspection.get("messages")
    raw_enums = inspection.get("enums")
    raw_dependencies = inspection.get("dependencies")
    if (
        not isinstance(raw_files, list)
        or not isinstance(raw_messages, list)
        or not isinstance(raw_enums, list)
        or not isinstance(raw_dependencies, dict)
    ):
        raise SchemaResolutionError("Inspection report is missing required descriptor indexes.")
    available_files = {
        str(item["name"]) for item in raw_files if isinstance(item, dict) and "name" in item
    }
    dependencies = {
        str(name): [str(value) for value in values]
        for name, values in raw_dependencies.items()
        if isinstance(values, list)
    }
    symbol_files = {
        str(item["name"]): str(item["file"])
        for item in [*raw_messages, *raw_enums]
        if isinstance(item, dict) and "name" in item and "file" in item
    }

    resolved_symbols: dict[str, str] = {}
    for symbol in requirement.symbols:
        source = symbol_files.get(symbol)
        if source is None:
            raise SchemaResolutionError(
                f"Required symbol does not exist in SDK descriptor: {symbol}"
            )
        resolved_symbols[symbol] = source
    root_files = {_module_source(module, available_files) for module in requirement.modules}
    root_files.update(resolved_symbols.values())
    return SchemaGenerationPlan(
        features=selected_features,
        root_files=tuple(sorted(root_files)),
        dependency_closure=_closure(root_files, dependencies),
        resolved_symbols=resolved_symbols,
    )
