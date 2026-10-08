"""Presentation-only Raspberry Pi service status console."""

from __future__ import annotations

import os
import time
from datetime import datetime


def main() -> None:
    tick = 0
    while True:
        os.system("cls" if os.name == "nt" else "clear")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S KST")
        print("SMART CYLINDER SERVICE STATUS  (presentation mode)")
        print("=" * 82)
        print(f"Raspberry Pi IP: 192.168.137.99        Current: {now}")
        print("Mosquitto:       active (running)")
        print("smart-cylinder:  active (running)")
        print("MQTT port:       1883 LISTEN")
        print("SQLite queue:    0 pending")
        print("=" * 82)
        print("Recent service events")
        print(f"[{now}] MQTT connected; raw topic subscribed")
        print(f"[{now}] pico 01: raw packet committed sequence={980 + tick}")
        print(f"[{now}] analysis complete: vibration + sound fusion")
        print("\nThis is a local presentation screen; Ctrl+C to exit.")
        tick += 1
        time.sleep(2)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
