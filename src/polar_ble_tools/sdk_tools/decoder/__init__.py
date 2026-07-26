"""Build and manage the optional, locally compiled REC decoder sidecar."""

from __future__ import annotations

from importlib import import_module

__all__ = [
    "DecoderBuildError",
    "DecoderBuildResult",
    "activate_decoder",
    "build_decoder",
    "remove_decoder",
    "verify_decoder",
]


def __getattr__(name: str):
    if name in __all__ or name.startswith("_"):
        return getattr(import_module("polar_ble_tools.sdk_tools.decoder.lifecycle"), name)
    raise AttributeError(name)
