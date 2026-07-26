from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_data_path


def default_cache_root() -> Path:
    return user_data_path("polar-ble-tools", appauthor=False)


@dataclass(frozen=True)
class SdkCache:
    """The user-owned cache locations used by SDK tooling.

    All paths are outside the source tree and build artifacts.  The downloader
    is the sole writer for SDK checkout entries.
    """

    root: Path

    @classmethod
    def default(cls) -> SdkCache:
        return cls(default_cache_root())

    @property
    def sdk_root(self) -> Path:
        return self.root / "sdk" / "polar"

    @property
    def active_manifest_path(self) -> Path:
        return self.root / "active-sdk.json"

    def sdk_path(self, commit: str) -> Path:
        return self.sdk_root / commit

    @property
    def generated_root(self) -> Path:
        return self.root / "generated" / "polar"

    def generated_path(self, commit: str) -> Path:
        return self.generated_root / commit

    @property
    def decoder_build_root(self) -> Path:
        return self.root / "decoder-build" / "polar"

    @property
    def rec_jvm_toolchain_root(self) -> Path:
        """Persistent toolchains shared by all local REC decoder revisions."""
        return self.root / "toolchains" / "rec-jvm"

    def rec_jvm_java_home(self, platform: str, architecture: str, version: str) -> Path:
        return self.rec_jvm_toolchain_root / platform / architecture / f"jdk-{version}"

    @property
    def decoder_root(self) -> Path:
        return self.root / "decoder" / "polar"

    @property
    def active_decoder_manifest_path(self) -> Path:
        return self.root / "active-decoder.json"

    def decoder_build_path(self, commit: str) -> Path:
        return self.decoder_build_root / commit

    def decoder_path(self, commit: str) -> Path:
        return self.decoder_root / commit
