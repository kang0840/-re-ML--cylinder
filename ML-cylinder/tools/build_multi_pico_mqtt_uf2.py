"""Build Pico 01~04 standalone UF2 files for the multi-Pico MQTT design.

Network credentials are read from the existing per-board registration settings
only while staging a local build. They are frozen inside the UF2 and never
printed by this script.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
MICROPYTHON = ROOT / "third_party" / "micropython"
FIRMWARE = ROOT / "pico" / "multi_mqtt"
LEGACY_SETTINGS = ROOT / "pico" / "registration_firmware"
OUTPUT = ROOT / "outputs" / "multi_pico_mqtt_uf2"
# Kept deliberately short when invoked through a Windows SUBST drive; RP2040
# qstr generation otherwise exceeds the Windows process command-line limit.
BUILD_ROOT = ROOT / "b"
MAKE = ROOT / "third_party" / "gnumake-windows" / "gnumake-4.4.1-x64.exe"
ARM_BIN = Path(r"C:\Program Files (x86)\Arm GNU Toolchain arm-none-eabi\12.2 mpacbti-rel1\bin")
CMAKE_BIN = Path(r"C:\Program Files\CMake\bin")
WINLIBS_BIN = ROOT / "third_party" / "winlibs" / "mingw64" / "bin"
PICOTOOL = ROOT / "third_party" / "picotool"


def stage_settings(device: str) -> str:
    """Use existing deployed network/auth values, with the new unique ID."""
    source = (LEGACY_SETTINGS / f"settings-{device}.py").read_text(encoding="utf-8")
    values: dict[str, str] = {}
    for line in source.splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    required = ("WIFI_SSID", "WIFI_PASSWORD", "MQTT_BROKER", "MQTT_PORT",
                "MQTT_USERNAME", "MQTT_PASSWORD")
    missing = [key for key in required if key not in values]
    if missing:
        raise RuntimeError(f"{device} settings missing: {', '.join(missing)}")
    return "\n".join((
        f"WIFI_SSID = {values['WIFI_SSID']}",
        f"WIFI_PASSWORD = {values['WIFI_PASSWORD']}",
        f"MQTT_HOST = {values['MQTT_BROKER']}",
        f"MQTT_PORT = {values['MQTT_PORT']}",
        f'MQTT_CLIENT_ID = "cylinder_{device}"',
        f'DEVICE_ID = "{device}"',
        f"MQTT_USERNAME = {values['MQTT_USERNAME']}",
        f"MQTT_PASSWORD = {values['MQTT_PASSWORD']}",
        "PUBLISH_INTERVAL_SECONDS = 5",
        "",
    ))


def main() -> None:
    required_paths = (MICROPYTHON / "ports" / "rp2", MAKE, ARM_BIN, CMAKE_BIN,
                      WINLIBS_BIN, PICOTOOL)
    if not all(path.exists() for path in required_paths):
        raise SystemExit("MicroPython, ARM toolchain, CMake, Make, Ninja, or picotool is missing")
    mpy_cross = shutil.which("mpy-cross")
    if not mpy_cross:
        raise SystemExit("mpy-cross is missing")
    env = os.environ.copy()
    env["PATH"] = os.pathsep.join((str(MAKE.parent), str(CMAKE_BIN), str(WINLIBS_BIN),
                                    str(ARM_BIN), r"C:\Program Files\Git\usr\bin", env["PATH"]))
    env["SHELL"] = r"C:\Program Files\Git\usr\bin\sh.exe"
    env["PYTHON"] = sys.executable
    env["CC"] = str(WINLIBS_BIN / "gcc.exe")
    env["CXX"] = str(WINLIBS_BIN / "g++.exe")
    OUTPUT.mkdir(parents=True, exist_ok=True)

    # The RP2040 C/C++ image is identical for every board.  Reuse one CMake
    # tree and rebuild only the frozen settings module for each identity.
    stage = BUILD_ROOT / "pico01" / "modules"
    stage.mkdir(parents=True, exist_ok=True)
    shutil.copy2(FIRMWARE / "main.py", stage / "main.py")
    manifest = BUILD_ROOT / "pico01" / "manifest.py"
    manifest.write_text(
        'include("$(PORT_DIR)/boards/manifest.py")\nrequire("umqtt.simple")\n'
        f'freeze("{stage.as_posix()}", ("main.py", "settings.py"))\n', encoding="utf-8")
    build_dir = BUILD_ROOT / "pico01" / "build"
    configure = [
        str(CMAKE_BIN / "cmake.exe"), "-S", str(MICROPYTHON / "ports" / "rp2"),
        "-B", str(build_dir), "-G", "Unix Makefiles", "-DPICO_BUILD_DOCS=0",
        "-DMICROPY_BOARD=RPI_PICO_W",
        f"-DMICROPY_BOARD_DIR={MICROPYTHON / 'ports' / 'rp2' / 'boards' / 'RPI_PICO_W'}",
        f"-DMICROPY_FROZEN_MANIFEST={manifest}", f"-DCMAKE_MAKE_PROGRAM={MAKE}",
        f"-DPICOTOOL_GIT_REPOSITORY_URL=file:///{PICOTOOL.as_posix()}",
        "-DPICOTOOL_GIT_BRANCH=master", f"-DMPY_CROSS={mpy_cross}",
    ]
    if not (build_dir / "CMakeCache.txt").exists():
        subprocess.run(configure, check=True, env=env)

    for number in range(1, 5):
        device = f"pico{number:02d}"
        (stage / "settings.py").write_text(stage_settings(device), encoding="utf-8")
        print(f"Building {device} with client ID cylinder_{device}")
        subprocess.run([str(MAKE), "-C", str(build_dir)], check=True, env=env)
        uf2 = build_dir / "firmware.uf2"
        if not uf2.exists():
            raise RuntimeError(f"{device} did not produce firmware.uf2")
        target = OUTPUT / f"{device}_multi_mqtt.uf2"
        shutil.copy2(uf2, target)
        print(f"Created {target}")


if __name__ == "__main__":
    main()
