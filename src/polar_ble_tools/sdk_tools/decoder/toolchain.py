"""Pinned, architecture-specific toolchain facts for the REC decoder."""

from __future__ import annotations

import hashlib
import json
import os
import platform as host_platform
from dataclasses import asdict, dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from polar_ble_tools.schemas.cache import SdkCache


@dataclass(frozen=True)
class ToolchainDescriptor:
    platform: str
    architecture: str
    jdk_version: str
    jdk_archive_name: str
    jdk_url: str
    jdk_sha256: str
    jdk_archive_root: str
    java_relative_path: str
    gradle_version: str
    gradle_archive_name: str
    gradle_url: str
    gradle_sha256: str


_JDK_VERSION = "21.0.12+8"
_GRADLE_VERSION = "9.4.1"
_GRADLE_ARCHIVE = f"gradle-{_GRADLE_VERSION}-bin.zip"
_GRADLE_URL = f"https://services.gradle.org/distributions/{_GRADLE_ARCHIVE}"
_GRADLE_SHA256 = "2ab2958f2a1e51120c326cad6f385153bb11ee93b3c216c5fccebfdfbb7ec6cb"
_TEMURIN_RELEASE = (
    "https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.12%2B8"
)


def _descriptor(architecture: str, archive_architecture: str, sha256: str) -> ToolchainDescriptor:
    archive = f"OpenJDK21U-jdk_{archive_architecture}_linux_hotspot_21.0.12_8.tar.gz"
    return ToolchainDescriptor(
        platform="linux",
        architecture=architecture,
        jdk_version=_JDK_VERSION,
        jdk_archive_name=archive,
        jdk_url=f"{_TEMURIN_RELEASE}/{archive}",
        jdk_sha256=sha256,
        jdk_archive_root=f"jdk-{_JDK_VERSION}",
        java_relative_path="bin/java",
        gradle_version=_GRADLE_VERSION,
        gradle_archive_name=_GRADLE_ARCHIVE,
        gradle_url=_GRADLE_URL,
        gradle_sha256=_GRADLE_SHA256,
    )


TOOLCHAIN_DESCRIPTORS: Mapping[tuple[str, str], ToolchainDescriptor] = MappingProxyType(
    {
        ("linux", "x86_64"): _descriptor(
            "x86_64",
            "x64",
            "e4446ff06a276155697597cc0f1b15da004ff083f4964a35271ecee567177370",
        ),
        ("linux", "aarch64"): _descriptor(
            "aarch64",
            "aarch64",
            "eba38e871b02d407897bfe017ea35352dfc1420ef6d2112425b0c67325ca509d",
        ),
    }
)


def normalized_platform(value: str | None = None) -> str:
    return (value if value is not None else host_platform.system()).strip().lower()


def normalized_architecture(value: str | None = None) -> str:
    architecture = (value if value is not None else host_platform.machine()).strip().lower()
    return {
        "amd64": "x86_64",
        "x64": "x86_64",
        "arm64": "aarch64",
    }.get(architecture, architecture)


def toolchain_descriptor(
    platform: str | None = None, architecture: str | None = None
) -> ToolchainDescriptor:
    key = (normalized_platform(platform), normalized_architecture(architecture))
    try:
        return TOOLCHAIN_DESCRIPTORS[key]
    except KeyError as exc:
        raise RuntimeError(
            "REC decoder builds support Linux x86_64 and Linux aarch64; "
            f"the current host is {key[0]}/{key[1]}."
        ) from exc


def toolchain_descriptor_digest(descriptor: ToolchainDescriptor) -> str:
    payload = json.dumps(asdict(descriptor), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def java_home(cache: SdkCache, descriptor: ToolchainDescriptor) -> Path:
    return cache.rec_jvm_java_home(
        descriptor.platform,
        descriptor.architecture,
        descriptor.jdk_version,
    )


def java_executable(cache: SdkCache, descriptor: ToolchainDescriptor) -> Path:
    return java_home(cache, descriptor) / descriptor.java_relative_path


def java_environment(
    java_home_path: Path, *, java_relative_path: str = "bin/java"
) -> dict[str, str]:
    executable = java_home_path / java_relative_path
    if not executable.is_file() or executable.is_symlink():
        raise RuntimeError(
            "Pinned REC decoder JDK is missing or unsafe; rebuild with: polar-ble sdk decoder build"
        )
    environment = os.environ.copy()
    environment["JAVA_HOME"] = str(java_home_path)
    environment["PATH"] = f"{executable.parent}:{environment.get('PATH', '')}"
    return environment
