"""Presentation-only Pico 1~6 sensor monitor for a local Windows console."""

from __future__ import annotations

import os
import time
from datetime import datetime


def main() -> None:
    sequence = 1
    while True:
        os.system("cls" if os.name == "nt" else "clear")
        print("PICO SENSOR MONITOR  (presentation mode; Ctrl+C to exit)")
        print(f"MQTT broker: 192.168.137.99:1883   Updated: {datetime.now():%Y-%m-%d %H:%M:%S}")
        print("Pico     Status     Time       Sensor       Seq        Min       Max       RMS      Note")
        print("-" * 96)
        for number in range(1, 7):
            sensor = "inmp441" if number % 2 else "sph0645"
            rms = 720000 + number * 12500 + sequence * 350
            print(f"pico{number:02d}   ONLINE     {datetime.now():%H:%M:%S}   {sensor:<11} {sequence:>5}  {-rms:>9,} {rms:>9,} {rms:>9,}   QoS 1")
        print("\nAll Pico devices are shown in local presentation mode.")
        sequence += 1
        time.sleep(2)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
