from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType, SimpleNamespace

from polar_ble_tools.schemas.cache import SdkCache
from polar_ble_tools.schemas.errors import SchemaUnavailableError
from polar_ble_tools.sdk_tools.downloader import SdkDownloadError
from polar_ble_tools.sdk_tools.verifier import SchemaVerificationError, verify_schemas


@dataclass
class SchemaActivationManager:
    """The sole runtime boundary for generated protobuf modules.

    Switching revisions after a generated module has been imported is rejected:
    protobuf descriptor registration is process-global and unloading it is not a
    safe operation.  This deliberately makes a process commit-sticky.
    """

    cache: SdkCache
    active_commit: str | None = None
    active_generated_root: Path | None = None
    loaded_module_names: set[str] = field(default_factory=set)

    def require(self, *modules: str) -> SimpleNamespace:
        try:
            root = verify_schemas(cache=self.cache)
            from polar_ble_tools.sdk_tools.downloader import active_sdk_source

            commit, _ = active_sdk_source(cache=self.cache)
            self._activate(commit, root)
            imported = {name: self._import_from_active_root(name) for name in modules}
            return SimpleNamespace(**imported)
        except (SdkDownloadError, SchemaVerificationError, ImportError, OSError, ValueError) as exc:
            raise SchemaUnavailableError(
                "Polar protobuf schemas are not installed or are invalid. Run: polar-ble sdk install --accept-license"
            ) from exc

    def _activate(self, commit: str, root: Path) -> None:
        root = root.resolve()
        if self.active_commit is not None and self.active_commit != commit:
            raise SchemaUnavailableError(
                f"Generated schemas for {self.active_commit} are already loaded; start a new process before switching to {commit}."
            )
        self.active_commit = commit
        self.active_generated_root = root

    def _import_from_active_root(self, module: str) -> ModuleType:
        if self.active_generated_root is None:
            raise SchemaUnavailableError("No generated schema root is active.")
        existing = sys.modules.get(module)
        if existing is not None:
            self._assert_module_path(module, existing)
            self.loaded_module_names.add(module)
            return existing
        root_text = str(self.active_generated_root)
        sys.path.insert(0, root_text)
        try:
            imported = importlib.import_module(module)
        finally:
            # Do not permanently mutate import precedence.  Imported modules
            # retain their resolved definitions in sys.modules.
            try:
                sys.path.remove(root_text)
            except ValueError:  # pragma: no cover - external mutation
                pass
        self._assert_module_path(module, imported)
        for name, candidate in tuple(sys.modules.items()):
            if getattr(candidate, "__file__", None) is None:
                continue
            try:
                Path(candidate.__file__).resolve().relative_to(self.active_generated_root)
            except ValueError:
                continue
            self.loaded_module_names.add(name)
        return imported

    def _assert_module_path(self, name: str, module: ModuleType) -> None:
        source = getattr(module, "__file__", None)
        if source is None or self.active_generated_root is None:
            raise SchemaUnavailableError(
                f"Generated module {name} has no file inside the active cache."
            )
        try:
            Path(source).resolve().relative_to(self.active_generated_root)
        except ValueError as exc:
            raise SchemaUnavailableError(
                f"Generated module {name} was loaded outside the active cache."
            ) from exc

    def ensure_removable(self, commit: str | None) -> None:
        if self.active_commit is not None and (commit is None or self.active_commit == commit):
            raise SchemaUnavailableError(
                "Cannot remove the active generated cache after schemas are loaded; start a new process first."
            )


_MANAGERS: dict[Path, SchemaActivationManager] = {}


def schema_activation_manager(cache: SdkCache | None = None) -> SchemaActivationManager:
    cache = cache or SdkCache.default()
    key = cache.root.resolve()
    return _MANAGERS.setdefault(key, SchemaActivationManager(cache))


def require_modules(*modules: str) -> SimpleNamespace:
    return schema_activation_manager().require(*modules)
