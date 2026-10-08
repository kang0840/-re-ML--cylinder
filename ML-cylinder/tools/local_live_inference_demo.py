"""Windows-local live inference console for presentation screenshots.

It visualises the Smart Cylinder monitor without a connected Raspberry Pi or
sensor.  Values are intentionally marked as a local demonstration.
"""

from __future__ import annotations

import math
import os
import time
from datetime import datetime


try:
    import msvcrt
except ImportError:  # pragma: no cover - this launcher targets Windows
    msvcrt = None


def clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def render(sequence: int, manual_state: str, typed: str) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S KST")
    vibration_rms = 1_720_000 + int(math.sin(sequence / 4) * 42_000)
    sound_rms = 735_000 + int(math.cos(sequence / 3) * 35_000)
    vibration_result = "seal_leak" if sequence % 7 else "normal"
    sound_result = "internal_wear" if sequence % 5 else "normal"
    overall = "internal_wear" if sound_result != "normal" else vibration_result
    color = "\033[91m" if manual_state == "OFF" else "\033[92m"
    reset = "\033[0m"
    clear()
    print("스마트 실린더 실시간 추론 (진동 + 소리)")
    print("=" * 112)
    print(f"수동 테스트: {color}● {manual_state}{reset} (실제 PLC 출력 아님) | 현재: {now} | 변경: -")
    print(f"서비스: mosquitto=active  smart-cylinder=active | 측정={980 + sequence * 2} 추론={980 + sequence * 2} 통합={490 + sequence} 수신대기=0")
    print("-" * 112)
    print(f"{'구분':<6} {'센서':<12} {'시각':<10} {'순번':>7} {'RMS':>13} {'Crest':>8} {'주파수':>10} {'판정':<16} {'신뢰도':>7} {'건강도':>7}")
    print("-" * 112)
    print(f"{'진동':<6} {'sph0645':<12} {now[11:19]:<10} {sequence:>7} {vibration_rms:>13,.1f} {4.49:>8.2f} {'250.0Hz':>10} {vibration_result:<16} {1.00:>7.2f} {62.0:>7.1f}")
    print("       모델=pycaret-single-dt-demo | PyCaret=비교 전 (presentation mode)")
    print(f"{'소리':<6} {'inmp441':<12} {now[11:19]:<10} {sequence:>7} {sound_rms:>13,.1f} {9.22:>8.2f} {'7250.0Hz':>10} {sound_result:<16} {1.00:>7.2f} {45.0:>7.1f}")
    print("       모델=pycaret-single-dt-demo | PyCaret=비교 전 (presentation mode)")
    print("=" * 112)
    print(f"통합 판정: {now} / sequence={sequence} / 판정={overall} / 신뢰도=1.00 / 건강도=45.0")
    print()
    print("명령: ON=켜기, OFF=끄기, EXIT=종료")
    print(f"명령 입력 > {typed}", end="", flush=True)


def main() -> None:
    sequence = 1
    manual_state = "OFF"
    typed = ""
    while True:
        render(sequence, manual_state, typed)
        until = time.monotonic() + 2
        while time.monotonic() < until:
            if msvcrt and msvcrt.kbhit():
                key = msvcrt.getwch()
                if key in ("\r", "\n"):
                    command = typed.strip().upper()
                    if command == "EXIT":
                        print("\n실시간 추론 화면을 종료합니다.")
                        return
                    if command in {"ON", "OFF"}:
                        manual_state = command
                    typed = ""
                    break
                if key == "\b":
                    typed = typed[:-1]
                elif key.isprintable():
                    typed += key
                render(sequence, manual_state, typed)
            time.sleep(0.03)
        sequence += 1


if __name__ == "__main__":
    main()
