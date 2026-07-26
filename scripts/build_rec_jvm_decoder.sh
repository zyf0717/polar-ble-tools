#!/usr/bin/env bash
# Build the local-only REC decoder sidecar from a separately staged Polar SDK.

set -euo pipefail

usage() {
    cat <<'EOF'
Usage: scripts/build_rec_jvm_decoder.sh --sdk-source PATH [--root PATH]

Build a local `polar-rec-decoder` distribution from the supplied cached Polar
SDK source tree. Run scripts/setup_rec_jvm_spike.sh first. No SDK source or
decoder output is written into this repository.
EOF
}

require_command() {
    command -v "$1" >/dev/null || {
        echo "missing required command: $1" >&2
        exit 1
    }
}

default_root() {
    python3 - <<'PY'
from pathlib import Path
import os

data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
print(data_home / "polar-ble-tools" / "rec-jvm-spike")
PY
}

sdk_source=""
root="$(default_root)"
while (($#)); do
    case "$1" in
        --sdk-source)
            (($# >= 2)) || { usage >&2; exit 2; }
            sdk_source="$2"
            shift 2
            ;;
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

[[ -n "$sdk_source" ]] || { usage >&2; exit 2; }
require_command python3
root="$(python3 -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).expanduser().resolve())' "$root")"
sdk_source="$(python3 -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).expanduser().resolve())' "$sdk_source")"
readonly root sdk_source
[[ -d "$sdk_source" ]] || { echo "SDK source does not exist: $sdk_source" >&2; exit 1; }
[[ -f "$sdk_source/com/polar/androidcommunications/api/ble/model/offlinerecording/OfflineRecordingData.kt" ]] || {
    echo "SDK source does not contain OfflineRecordingData.kt: $sdk_source" >&2
    exit 1
}

java_home="${root}/tools/jdk-21.0.12+8"
gradle="${root}/tools/gradle-9.4.1/bin/gradle"
[[ -x "${java_home}/bin/java" && -x "$gradle" ]] || {
    echo "run scripts/setup_rec_jvm_spike.sh before building the decoder" >&2
    exit 1
}

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
template_root="${repo_root}/src/polar_ble_tools/sdk_tools/decoder_project"
workspace="${root}/decoder-workspace"
distribution="${root}/decoder-dist"
rm -rf "$workspace" "$distribution"
mkdir -p "${workspace}/src/main/kotlin"
cp "${template_root}/settings.gradle.kts" "${workspace}/settings.gradle.kts"
cp "${template_root}/build.gradle.kts" "${workspace}/build.gradle.kts"
cp "${template_root}/DecoderMain.kt" "${workspace}/src/main/kotlin/DecoderMain.kt"

JAVA_HOME="$java_home" \
GRADLE_USER_HOME="${root}/gradle-user-home" \
"$gradle" --no-daemon --project-dir "$workspace" -PpolarSdkSource="$sdk_source" installDist

mv "${workspace}/build/install/polar-rec-decoder" "$distribution"
printf '%s\n' "built local decoder: ${distribution}/bin/polar-rec-decoder"
