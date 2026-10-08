"""Terminal-friendly A/B cylinder capture using Raspberry Pi's rpicam-still.

This fallback does not need OpenCV.  Each Enter press captures a batch of
images and writes full-frame YOLO annotations for a single, tightly framed
cylinder.
"""

from __future__ import annotations

import argparse
import subprocess
import time
from pathlib import Path


CLASSES = ("A_CYLINDER", "B_CYLINDER")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture A/B cylinder YOLO images")
    parser.add_argument("--class", dest="class_name", choices=CLASSES, required=True)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--output", type=Path, default=Path("datasets/cylinder_yolo/raw"))
    parser.add_argument("--count", type=int, default=100, help="images to save per Enter press")
    parser.add_argument("--interval", type=float, default=0.2, help="seconds between captures")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    class_id = CLASSES.index(args.class_name)
    image_dir = args.output / "images" / args.class_name
    label_dir = args.output / "labels" / args.class_name
    image_dir.mkdir(parents=True, exist_ok=True)
    label_dir.mkdir(parents=True, exist_ok=True)

    if args.count < 1 or args.interval < 0:
        raise ValueError("--count must be positive and --interval cannot be negative")
    print(f"Capturing {args.class_name}. Place one cylinder to fill most of the frame.")
    print(f"Press Enter to capture {args.count} images; type q then Enter to finish.")
    count = 0
    while True:
        if input("> ").strip().lower() == "q":
            break
        for batch_index in range(args.count):
            stem = f"{args.class_name.lower()}_{time.strftime('%Y%m%d_%H%M%S')}_{time.time_ns() % 1_000_000:06d}"
            image_path = image_dir / f"{stem}.jpg"
            subprocess.run(
                [
                    "rpicam-still", "-n", "-t", "300",
                    "--width", str(args.width), "--height", str(args.height),
                    "-o", str(image_path),
                ],
                check=True,
            )
            (label_dir / f"{stem}.txt").write_text(
                f"{class_id} 0.5 0.5 1.0 1.0\n", encoding="utf-8"
            )
            count += 1
            if (batch_index + 1) % 10 == 0 or batch_index + 1 == args.count:
                print(f"batch: {batch_index + 1}/{args.count}, total saved: {count}")
            if args.interval:
                time.sleep(args.interval)


if __name__ == "__main__":
    main()
