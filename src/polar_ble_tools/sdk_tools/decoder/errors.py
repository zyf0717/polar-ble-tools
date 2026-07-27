"""Stable SDK decoder lifecycle error categories."""

from __future__ import annotations


class SdkLifecycleError(RuntimeError):
    """The local SDK-backed decoder lifecycle cannot proceed safely."""


class LicenseAcceptanceRequiredError(SdkLifecycleError):
    """The staged SDK has no content-bound licence acceptance."""


class LicenseAcceptanceMismatchError(SdkLifecycleError):
    """The staged SDK no longer matches its accepted licence record."""


class LicenseNoticeMissingError(SdkLifecycleError):
    """Required decoder-local licence or notice material is absent."""


class LicenseNoticeMismatchError(SdkLifecycleError):
    """Decoder-local licence or notice material failed verification."""
