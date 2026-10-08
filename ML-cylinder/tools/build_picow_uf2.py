"""Build one self-contained Raspberry Pi Pico W UF2 per Pico MQTT identity."""
from __future__ import annotations

import shutil
import subprocess
import os
import sys
from pathlib import Path


# Do not resolve a Windows SUBST drive: its short path prevents command-line
# length failures in the RP2040 qstr generation step.
ROOT = Path(__file__).parents[1]
MICROPYTHON = ROOT / "third_party" / "micropython"
FIRMWARE = ROOT / "pico" / "registration_firmware"
OUTPUT = ROOT / "outputs" / "pico_w_uf2"
# Keep a fresh build tree while transitioning host compilers.  The prior
# directory may contain a nested Pico SDK CMake cache that pins clang.
BUILD_ROOT = ROOT / "build" / "pico_w_uf2_make_short"
MAKE = ROOT / "third_party" / "gnumake-windows" / "gnumake-4.4.1-x64.exe"
ARM_BIN = Path(r"C:\Program Files (x86)\Arm GNU Toolchain arm-none-eabi\12.2 mpacbti-rel1\bin")
CMAKE_BIN = Path(r"C:\Program Files\CMake\bin")
LLVM_BIN = Path(r"C:\Program Files\LLVM\bin")
WINLIBS_BIN = ROOT / "third_party" / "winlibs" / "mingw64" / "bin"
NINJA = WINLIBS_BIN / "ninja.exe"
PICOTOOL = ROOT / "third_party" / "picotool"


def main() -> None:
    if not (MICROPYTHON / "ports" / "rp2").exists():
        raise SystemExit("MicroPython Pico W source is missing")
    if not MAKE.exists() or not NINJA.exists() or not ARM_BIN.exists() or not CMAKE_BIN.exists() or not WINLIBS_BIN.exists() or not PICOTOOL.exists():
        raise SystemExit("GNU Make, Ninja, CMake, ARM GNU Toolchain, or picotool source is missing")
    mpy_cross = shutil.which("mpy-cross")
    if not mpy_cross:
        raise SystemExit("mpy-cross is missing")

    env = os.environ.copy()
    env["PATH"] = os.pathsep.join([str(MAKE.parent), str(CMAKE_BIN), str(WINLIBS_BIN), str(ARM_BIN), r"C:\Program Files\Git\usr\bin", env["PATH"]])
    env["SHELL"] = r"C:\Program Files\Git\usr\bin\sh.exe"
    # MicroPython's nested mpy-cross makefile invokes this name directly.
    env["PYTHON"] = sys.executable
    env["CC"] = str(WINLIBS_BIN / "gcc.exe")
    env["CXX"] = str(WINLIBS_BIN / "g++.exe")
    OUTPUT.mkdir(parents=True, exist_ok=True)

    for number in range(1, 7):
        device = f"pico{number:02d}"
        stage = BUILD_ROOT / device / "modules"
        stage.mkdir(parents=True, exist_ok=True)
        shutil.copy2(FIRMWARE / "main.py", stage / "main.py")
        shutil.copy2(FIRMWARE / f"settings-{device}.py", stage / "settings.py")
        manifest = BUILD_ROOT / device / "manifest.py"
        modules = stage.as_posix()
        manifest.write_text(
            'include("$(PORT_DIR)/boards/manifest.py")\n'
            'require("umqtt.simple")\n'
            f'freeze("{modules}", ("main.py", "settings.py"))\n',
            encoding="utf-8",
        )
        build_dir = BUILD_ROOT / device / "build"
        configure = [
            str(CMAKE_BIN / "cmake.exe"), "-S", str(MICROPYTHON / "ports" / "rp2"), "-B", str(build_dir),
            "-G", "Unix Makefiles", "-DPICO_BUILD_DOCS=0", "-DMICROPY_BOARD=RPI_PICO_W",
            f"-DMICROPY_BOARD_DIR={MICROPYTHON / 'ports' / 'rp2' / 'boards' / 'RPI_PICO_W'}",
            f"-DMICROPY_FROZEN_MANIFEST={manifest}", f"-DCMAKE_MAKE_PROGRAM={MAKE}",
            f"-DPICOTOOL_GIT_REPOSITORY_URL=file:///{PICOTOOL.as_posix()}",
            "-DPICOTOOL_GIT_BRANCH=master",
            f"-DMPY_CROSS={mpy_cross}",
        ]
        command = [str(MAKE), "-C", str(build_dir)]
        print("Building", device)
        subprocess.run(configure, check=True, env=env)
        subprocess.run(command, check=True, env=env)
        uf2 = build_dir / "firmware.uf2"
        if not uf2.exists():
            raise SystemExit(f"UF2 was not produced for {device}: {uf2}")
        shutil.copy2(uf2, OUTPUT / f"{device}_mqtt.uf2")
        print("Created", OUTPUT / f"{device}_mqtt.uf2")


if __name__ == "__main__":
    main()
