"""Train an A/B cylinder YOLO model. Prefer a PC with an NVIDIA GPU."""

from __future__ import annotations

import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the cylinder YOLO model")
    parser.add_argument("--data", default="config/cylinder_yolo_dataset.yaml")
    parser.add_argument("--model", default="yolo11n.pt")
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=-1)
    parser.add_argument("--device", default=None, help="0 for first GPU; cpu for CPU")
    parser.add_argument("--project", default="runs/cylinder_yolo")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    from ultralytics import YOLO

    model = YOLO(args.model)
    result = model.train(data=args.data, epochs=args.epochs, imgsz=args.imgsz, batch=args.batch, device=args.device, project=args.project, name="ab_cylinder")
    best = Path(result.save_dir) / "weights" / "best.pt"
    print(f"training complete; copy this to the Pi: {best}")


if __name__ == "__main__":
    main()
