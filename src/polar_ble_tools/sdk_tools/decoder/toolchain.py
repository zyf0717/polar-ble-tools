"""Pinned toolchain facts and runtime environment for the REC decoder."""

from __future__ import annotations

import os
import platform as host_platform
from pathlib import Path

from polar_ble_tools.schemas.cache import SdkCache

JDK_VERSION = "21.0.12+8"
GRADLE_VERSION = "9.4.1"
JDK_ARCHIVE = "OpenJDK21U-jdk_x64_linux_hotspot_21.0.12_8.tar.gz"
GRADLE_ARCHIVE = f"gradle-{GRADLE_VERSION}-bin.zip"
JDK_URL = (
    "https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.12%2B8/"
    f"{JDK_ARCHIVE}"
)
GRADLE_URL = f"https://services.gradle.org/distributions/{GRADLE_ARCHIVE}"
JDK_SHA256 = "e4446ff06a276155697597cc0f1b15da004ff083f4964a35271ecee567177370"
GRADLE_SHA256 = "2ab2958f2a1e51120c326cad6f385153bb11ee93b3c216c5fccebfdfbb7ec6cb"


def normalized_platform() -> str:
    return host_platform.system().lower()


def normalized_architecture() -> str:
    architecture = host_platform.machine().lower()
    return "x86_64" if architecture == "amd64" else architecture


def java_home(cache: SdkCache, *, platform: str, architecture: str, version: str) -> Path:
    return cache.rec_jvm_java_home(platform, architecture, version)


def java_executable(cache: SdkCache, *, platform: str, architecture: str, version: str) -> Path:
    return (
        java_home(cache, platform=platform, architecture=architecture, version=version)
        / "bin"
        / "java"
    )


def java_environment(java_home_path: Path) -> dict[str, str]:
    executable = java_home_path / "bin" / "java"
    if not executable.is_file() or executable.is_symlink():
        raise RuntimeError(
            "Pinned REC decoder JDK is missing or unsafe; rebuild the active decoder."
        )
    environment = os.environ.copy()
    environment["JAVA_HOME"] = str(java_home_path)
    environment["PATH"] = f"{java_home_path / 'bin'}:{environment.get('PATH', '')}"
    return environment
