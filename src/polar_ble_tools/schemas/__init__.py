"""Local schema-cache infrastructure.

Schema activation is intentionally added after generation support exists.
"""

from polar_ble_tools.schemas.cache import SdkCache
from polar_ble_tools.schemas.requirements import FEATURE_REQUIREMENTS, requirements_for

__all__ = ["FEATURE_REQUIREMENTS", "SdkCache", "require_modules", "requirements_for"]


def require_modules(*modules: str):
    """Lazily activate generated schemas only for schema-backed operations."""
    from polar_ble_tools.schemas.runtime import require_modules as _require_modules

    return _require_modules(*modules)
