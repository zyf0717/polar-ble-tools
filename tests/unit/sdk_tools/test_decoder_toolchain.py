from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from polar_ble_tools.sdk_tools.decoder.toolchain import (
    TOOLCHAIN_DESCRIPTORS,
    normalized_architecture,
    normalized_platform,
    toolchain_descriptor,
    toolchain_descriptor_digest,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("AMD64", "x86_64"),
        ("amd64", "x86_64"),
        ("x86_64", "x86_64"),
        ("AArch64", "aarch64"),
        ("arm64", "aarch64"),
        ("aarch64", "aarch64"),
    ],
)
def test_architecture_aliases_are_normalized(raw: str, expected: str) -> None:
    assert normalized_architecture(raw) == expected


def test_platform_is_normalized() -> None:
    assert normalized_platform("Linux") == "linux"
    assert normalized_platform("Windows") == "windows"


def test_descriptors_are_immutable_and_architecture_specific() -> None:
    x86 = toolchain_descriptor("Linux", "AMD64")
    arm = toolchain_descriptor("linux", "arm64")
    mac = toolchain_descriptor("Darwin", "arm64")
    windows = toolchain_descriptor("Windows", "AMD64")

    assert x86.architecture == "x86_64"
    assert arm.architecture == "aarch64"
    assert x86.jdk_archive_name != arm.jdk_archive_name
    assert x86.jdk_sha256 != arm.jdk_sha256
    assert x86.gradle_sha256 == arm.gradle_sha256
    assert mac.java_relative_path == "Contents/Home/bin/java"
    assert windows.jdk_archive_name.endswith("_windows_hotspot_21.0.12_8.zip")
    assert windows.java_relative_path == "bin/java.exe"
    assert len(toolchain_descriptor_digest(x86)) == 64
    assert toolchain_descriptor_digest(x86) != toolchain_descriptor_digest(arm)
    with pytest.raises(FrozenInstanceError):
        x86.architecture = "changed"  # type: ignore[misc]
    with pytest.raises(TypeError):
        TOOLCHAIN_DESCRIPTORS[("linux", "other")] = x86  # type: ignore[index]


def test_unsupported_host_has_actionable_error() -> None:
    with pytest.raises(RuntimeError, match="Windows on x86_64"):
        toolchain_descriptor("windows", "arm64")
