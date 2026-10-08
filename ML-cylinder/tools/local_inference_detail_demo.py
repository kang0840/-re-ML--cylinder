"""Presentation-only detailed model-result console."""

from __future__ import annotations

import os
import time
from datetime import datetime


def main() -> None:
    sequence = 1
    while True:
        os.system("cls" if os.name == "nt" else "clear")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print("SMART CYLINDER — INFERENCE RESULT DETAIL  (presentation mode)")
        print("=" * 104)
        print(f"Analysis time: {now} KST     Measurement sequence: {sequence}")
        print("-" * 104)
        print("[ VIBRATION / SPH0645 ]")
        print("  Model: pycaret-single-dt-demo     Prediction: seal_leak       Confidence: 1.00")
        print("  RMS: 1,745,254.6                 Crest factor: 4.49          Dominant: 250.0 Hz")
        print("  Health score: 62.0               Dataset role: vibration")
        print()
        print("[ SOUND / INMP441 ]")
        print("  Model: pycaret-single-dt-demo     Prediction: internal_wear   Confidence: 1.00")
        print("  RMS: 746,971.0                   Crest factor: 9.22          Dominant: 7250.0 Hz")
        print("  Health score: 45.0               Dataset role: sound")
        print("-" * 104)
        print("[ FUSION DECISION ]")
        print("  Overall prediction: internal_wear    Controlling role: sound    Fusion version: rule-v1")
        print("  Recommended action: inspection required")
        print("\nRefreshing every 2 seconds. Ctrl+C to exit.")
        sequence += 1
        time.sleep(2)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
