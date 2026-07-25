from __future__ import annotations

import ast
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from polar_ble_tools.schemas.requirements import (
    UNUSED_SCHEMA_MODULE_EXCEPTIONS,
    UNUSED_SCHEMA_SYMBOL_EXCEPTIONS,
    SchemaFeatureRequirement,
    requirements_for,
)


@dataclass(frozen=True)
class InferredSchemaRequirements:
    modules: tuple[str, ...]
    module_symbols: tuple[str, ...]


class SchemaRequirementDriftError(RuntimeError):
    """Raised when consumers and declared schema requirements disagree."""


@dataclass(frozen=True)
class SchemaRequirementReconciliation:
    inferred: InferredSchemaRequirements
    undeclared_modules: tuple[str, ...]
    stale_modules: tuple[str, ...]
    undeclared_symbols: tuple[str, ...]
    stale_symbols: tuple[str, ...]


class _SchemaReferenceVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.aliases: dict[str, str] = {}
        self.modules: set[str] = set()
        self.module_symbols: set[str] = set()

    def visit_Import(self, node: ast.Import) -> None:
        for imported in node.names:
            module = imported.name.rsplit(".", 1)[-1]
            if module.endswith("_pb2"):
                self.aliases[imported.asname or module] = module
                self.modules.add(module)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for imported in node.names:
            if imported.name.endswith("_pb2"):
                self.aliases[imported.asname or imported.name] = imported.name
                self.modules.add(imported.name)

    def visit_Assign(self, node: ast.Assign) -> None:
        # setup_payloads intentionally uses lazy string proxies so package
        # import remains schema-free.  Treat `_GeneratedModuleProxy("x_pb2")`
        # as the same declared dependency as a direct import.
        if (
            isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "_GeneratedModuleProxy"
            and len(node.value.args) == 1
            and isinstance(node.value.args[0], ast.Constant)
            and isinstance(node.value.args[0].value, str)
            and node.value.args[0].value.endswith("_pb2")
        ):
            module = node.value.args[0].value
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.aliases[target.id] = module
                    self.modules.add(module)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if isinstance(node.value, ast.Name):
            module = self.aliases.get(node.value.id)
            if module is not None and (node.attr.startswith("Pb") or node.attr[:1].isupper()):
                self.module_symbols.add(f"{module}.{node.attr}")
        self.generic_visit(node)


def scan_schema_references(paths: list[Path]) -> InferredSchemaRequirements:
    visitor = _SchemaReferenceVisitor()
    for path in sorted(paths):
        visitor.visit(ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))
    return InferredSchemaRequirements(
        modules=tuple(sorted(visitor.modules)),
        module_symbols=tuple(sorted(visitor.module_symbols)),
    )


def package_schema_consumer_paths() -> list[Path]:
    """Return schema consumers from package sources and relevant local tests.

    Wheels contain only the package tree; a source checkout additionally scans
    tests so a new schema reference cannot be introduced solely in a contract
    or contract test without updating the declaration.
    """
    package_root = Path(__file__).resolve().parents[1]
    paths = list(package_root.rglob("*.py"))
    repository_root = package_root.parents[1]
    tests_root = repository_root / "tests"
    if tests_root.is_dir():
        paths.extend(tests_root.rglob("*.py"))
    return sorted(paths)


def reconcile_schema_requirements(
    *,
    paths: list[Path] | None = None,
    requirement: SchemaFeatureRequirement | None = None,
    features: tuple[str, ...] = (),
    module_exceptions: Mapping[str, str] = UNUSED_SCHEMA_MODULE_EXCEPTIONS,
    symbol_exceptions: Mapping[str, str] = UNUSED_SCHEMA_SYMBOL_EXCEPTIONS,
) -> SchemaRequirementReconciliation:
    """Require every schema consumer/declaration to be intentional.

    Descriptor names use package-qualified symbols while source accesses module
    attributes.  Their final name component is the stable project-owned
    reconciliation boundary; descriptor resolution subsequently verifies the
    full package-qualified name.
    """
    inferred = scan_schema_references(paths or package_schema_consumer_paths())
    requirement = requirement or requirements_for(*features)
    declared_modules = set(requirement.modules)
    declared_symbols = set(requirement.symbols)
    inferred_symbol_names = {symbol.rsplit(".", 1)[-1] for symbol in inferred.module_symbols}
    declared_symbol_names = {symbol.rsplit(".", 1)[-1] for symbol in declared_symbols}

    undeclared_modules = tuple(sorted(set(inferred.modules) - declared_modules))
    stale_modules = tuple(sorted(declared_modules - set(inferred.modules) - set(module_exceptions)))
    undeclared_symbols = tuple(sorted(inferred_symbol_names - declared_symbol_names))
    stale_symbols = tuple(
        sorted(
            symbol
            for symbol in declared_symbols
            if symbol.rsplit(".", 1)[-1] not in inferred_symbol_names
            and symbol not in symbol_exceptions
        )
    )
    result = SchemaRequirementReconciliation(
        inferred=inferred,
        undeclared_modules=undeclared_modules,
        stale_modules=stale_modules,
        undeclared_symbols=undeclared_symbols,
        stale_symbols=stale_symbols,
    )
    if any((undeclared_modules, stale_modules, undeclared_symbols, stale_symbols)):
        details = []
        for label, values in (
            ("undeclared modules", undeclared_modules),
            ("stale modules", stale_modules),
            ("undeclared symbols", undeclared_symbols),
            ("stale symbols", stale_symbols),
        ):
            if values:
                details.append(f"{label}: {', '.join(values)}")
        raise SchemaRequirementDriftError(
            "Schema requirement reconciliation failed: " + "; ".join(details)
        )
    return result
