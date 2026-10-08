#!/usr/bin/env bash
# Build one standalone Pico W UF2 per MQTT identity under WSL/Linux.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
MICROPYTHON="$ROOT/third_party/micropython"
FIRMWARE="$ROOT/pico/registration_firmware"
OUTPUT="$ROOT/outputs/pico_w_uf2"
# WSL's native filesystem is dramatically faster for the many CMake objects.
# The finished UF2 files are still copied back to the Windows workspace.
BUILD_ROOT="${WSL_BUILD_ROOT:-/tmp/pico_w_uf2_wsl}"

mkdir -p "$OUTPUT"

for number in 01 02 03 04 05 06; do
    device="pico${number}"
    stage="$BUILD_ROOT/$device/modules"
    build_dir="$BUILD_ROOT/$device/build"
    manifest="$BUILD_ROOT/$device/manifest.py"

    mkdir -p "$stage"
    cp "$FIRMWARE/main.py" "$stage/main.py"
    cp "$FIRMWARE/settings-$device.py" "$stage/settings.py"
    {
        echo 'include("$(PORT_DIR)/boards/manifest.py")'
        echo 'require("umqtt.simple")'
        printf 'freeze("%s", ("main.py", "settings.py"))\n' "$stage"
    } > "$manifest"

    echo "Building $device"
    cmake -S "$MICROPYTHON/ports/rp2" -B "$build_dir" \
        -G "Unix Makefiles" \
        -DPICO_BUILD_DOCS=0 \
        -DMICROPY_BOARD=RPI_PICO_W \
        -DMICROPY_BOARD_DIR="$MICROPYTHON/ports/rp2/boards/RPI_PICO_W" \
        -DMICROPY_FROZEN_MANIFEST="$manifest"
    cmake --build "$build_dir" --parallel 2
    cp "$build_dir/firmware.uf2" "$OUTPUT/${device}_mqtt.uf2"
    echo "Created $OUTPUT/${device}_mqtt.uf2"
done
