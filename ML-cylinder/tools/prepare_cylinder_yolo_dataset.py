"""Validate and split captured A/B cylinder images into a YOLO dataset."""

from __future__ import annotations

import argparse
import random
import shutil
from pathlib import Path


CLASSES = ("A_CYLINDER", "B_CYLINDER")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare A/B cylinder YOLO train/validation folders")
    parser.add_argument("--source", type=Path, default=Path("datasets/cylinder_yolo/raw"))
    parser.add_argument("--output", type=Path, default=Path("datasets/cylinder_yolo"))
    parser.add_argument("--validation-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not 0 < args.validation_ratio < 1:
        raise ValueError("--validation-ratio must be between 0 and 1")
    randomizer = random.Random(args.seed)
    totals: dict[str, int] = {}
    for class_name in CLASSES:
        images = sorted((args.source / "images" / class_name).glob("*.jpg"))
        if len(images) < 10:
            raise ValueError(f"{class_name} needs at least 10 images; found {len(images)}")
        randomizer.shuffle(images)
        split_at = max(1, round(len(images) * (1 - args.validation_ratio)))
        for split, members in (("train", images[:split_at]), ("val", images[split_at:])):
            for image in members:
                label = args.source / "labels" / class_name / f"{image.stem}.txt"
                if not label.exists():
                    raise FileNotFoundError(f"Missing label: {label}")
                image_target = args.output / "images" / split / image.name
                label_target = args.output / "labels" / split / label.name
                image_target.parent.mkdir(parents=True, exist_ok=True)
                label_target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(image, image_target)
                shutil.copy2(label, label_target)
        totals[class_name] = len(images)
    print("dataset ready:", totals)


if __name__ == "__main__":
    main()
