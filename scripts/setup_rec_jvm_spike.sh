#!/usr/bin/env bash
# Provision the local toolchain for SPEC-001's pure-JVM feasibility spike.
#
# This script never downloads the Polar SDK and never writes to its checkout.
# It stores pinned, checksum-verified tools below the user data directory by
# default. Source this command's printed exports before invoking Gradle.

set -euo pipefail

readonly JDK_VERSION="21.0.12+8"
readonly JDK_ARCHIVE="OpenJDK21U-jdk_x64_linux_hotspot_21.0.12_8.tar.gz"
readonly JDK_URL="https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.12%2B8/${JDK_ARCHIVE}"
readonly JDK_SHA256="e4446ff06a276155697597cc0f1b15da004ff083f4964a35271ecee567177370"
readonly GRADLE_VERSION="9.4.1"
readonly GRADLE_ARCHIVE="gradle-${GRADLE_VERSION}-bin.zip"
readonly GRADLE_URL="https://services.gradle.org/distributions/${GRADLE_ARCHIVE}"
readonly GRADLE_SHA256="2ab2958f2a1e51120c326cad6f385153bb11ee93b3c216c5fccebfdfbb7ec6cb"

usage() {
    cat <<'EOF'
Usage: scripts/setup_rec_jvm_spike.sh [--root PATH]

Install the pinned JDK and Gradle distribution required for the local REC
decoder pure-JVM feasibility spike. The default root is:
  $XDG_DATA_HOME/polar-ble-tools/rec-jvm-spike
or ~/.local/share/polar-ble-tools/rec-jvm-spike when XDG_DATA_HOME is unset.

The command prints shell exports for JAVA_HOME, PATH, and GRADLE_USER_HOME.
EOF
}

default_root() {
    python3 - <<'PY'
from pathlib import Path
import os

data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
print(data_home / "polar-ble-tools" / "rec-jvm-spike")
PY
}

require_command() {
    command -v "$1" >/dev/null || {
        echo "missing required command: $1" >&2
        exit 1
    }
}

download_verified() {
    local url="$1"
    local expected_sha256="$2"
    local destination="$3"
    local temporary

    if [[ -f "$destination" ]] && echo "${expected_sha256}  ${destination}" | sha256sum --check --status -; then
        return
    fi
    rm -f "$destination"
    temporary="$(mktemp "${destination}.tmp.XXXXXX")"
    trap 'rm -f "$temporary"' RETURN
    curl --fail --location --retry 3 --silent --show-error --output "$temporary" "$url"
    echo "${expected_sha256}  ${temporary}" | sha256sum --check --status
    mv "$temporary" "$destination"
    trap - RETURN
}

install_jdk() {
    local tool_directory="$1"
    local archive_path="$2"
    local destination="${tool_directory}/jdk-${JDK_VERSION}"
    local staging

    if [[ -x "${destination}/bin/java" ]]; then
        return
    fi
    staging="$(mktemp -d "${tool_directory}/.jdk.XXXXXX")"
    trap 'rm -rf "$staging"' RETURN
    tar --extract --gzip --file "$archive_path" --strip-components=1 --directory "$staging"
    test -x "${staging}/bin/java"
    mv "$staging" "$destination"
    trap - RETURN
}

install_gradle() {
    local tool_directory="$1"
    local archive_path="$2"
    local destination="${tool_directory}/gradle-${GRADLE_VERSION}"
    local staging

    if [[ -x "${destination}/bin/gradle" ]]; then
        return
    fi
    staging="$(mktemp -d "${tool_directory}/.gradle.XXXXXX")"
    trap 'rm -rf "$staging"' RETURN
    unzip -q "$archive_path" -d "$staging"
    test -x "${staging}/gradle-${GRADLE_VERSION}/bin/gradle"
    mv "${staging}/gradle-${GRADLE_VERSION}" "$destination"
    trap - RETURN
}

root="$(default_root)"
while (($#)); do
    case "$1" in
        --root)
            (($# >= 2)) || { usage >&2; exit 2; }
            root="$2"
            shift 2
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            usage >&2
            exit 2
            ;;
    esac
done

[[ "$(uname --kernel-name)" == "Linux" ]] || {
    echo "only Linux x86_64 is supported by this feasibility setup script" >&2
    exit 1
}
[[ "$(uname --machine)" == "x86_64" ]] || {
    echo "only Linux x86_64 is supported by this feasibility setup script" >&2
    exit 1
}

for command in curl mktemp sha256sum tar unzip python3; do
    require_command "$command"
done

root="$(python3 -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).expanduser().resolve())' "$root")"
readonly root
readonly tools_root="${root}/tools"
readonly downloads_root="${root}/downloads"
mkdir -p "$tools_root" "$downloads_root" "${root}/gradle-user-home"

jdk_archive_path="${downloads_root}/${JDK_ARCHIVE}"
gradle_archive_path="${downloads_root}/${GRADLE_ARCHIVE}"
download_verified "$JDK_URL" "$JDK_SHA256" "$jdk_archive_path"
download_verified "$GRADLE_URL" "$GRADLE_SHA256" "$gradle_archive_path"
install_jdk "$tools_root" "$jdk_archive_path"
install_gradle "$tools_root" "$gradle_archive_path"

readonly java_home="${tools_root}/jdk-${JDK_VERSION}"
readonly gradle_home="${tools_root}/gradle-${GRADLE_VERSION}"
"${java_home}/bin/java" -version >&2
JAVA_HOME="$java_home" "${gradle_home}/bin/gradle" --version >&2

printf 'export REC_JVM_SPIKE_ROOT=%q\n' "$root"
printf 'export JAVA_HOME=%q\n' "$java_home"
printf 'export GRADLE_USER_HOME=%q\n' "${root}/gradle-user-home"
printf 'export PATH=%q\n' "${gradle_home}/bin:${java_home}/bin:${PATH}"
