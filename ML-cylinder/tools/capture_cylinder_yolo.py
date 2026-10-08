"""Capture labelled A/B cylinder images for a controlled YOLO dataset.

Use one class per capture run.  Press Space to save a frame and Q to finish.
The script writes an image plus an optional full-frame YOLO annotation.  The
automatic annotation is suitable only when one cylinder fills most of the
camera frame; otherwise use a bounding-box labelling tool before training.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path


CLASSES = ("A_CYLINDER", "B_CYLINDER")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture cylinder YOLO data")
    parser.add_argument("--class", dest="class_name", choices=CLASSES, required=True)
    parser.add_argument("--camera-backend", choices=("picamera2", "opencv"), default="picamera2")
    parser.add_argument("--device", type=int, default=0, help="USB camera index for opencv")
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--output", type=Path, default=Path("datasets/cylinder_yolo/raw"))
    parser.add_argument(
        "--full-frame-label",
        action="store_true",
        help="write class 0/1, 0.5 0.5 1.0 1.0 labels for tightly framed single cylinders",
    )
    return parser.parse_args()


def open_camera(args: argparse.Namespace):
    if args.camera_backend == "picamera2":
        from picamera2 import Picamera2

        camera = Picamera2()
        camera.configure(camera.create_preview_configuration(main={"size": (args.width, args.height), "format": "RGB888"}))
        camera.start()
        time.sleep(1)
        return camera

    import cv2

    camera = cv2.VideoCapture(args.device)
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    if not camera.isOpened():
        raise RuntimeError(f"Could not open /dev/video{args.device}")
    return camera


def main() -> None:
    import cv2

    args = parse_args()
    class_id = CLASSES.index(args.class_name)
    image_dir = args.output / "images" / args.class_name
    label_dir = args.output / "labels" / args.class_name
    image_dir.mkdir(parents=True, exist_ok=True)
    if args.full_frame_label:
        label_dir.mkdir(parents=True, exist_ok=True)

    camera = open_camera(args)
    count = 0
    try:
        while True:
            if args.camera_backend == "picamera2":
                frame = cv2.cvtColor(camera.capture_array(), cv2.COLOR_RGB2BGR)
            else:
                ok, frame = camera.read()
                if not ok:
                    raise RuntimeError("Camera frame could not be read")
            display = frame.copy()
            cv2.putText(display, f"{args.class_name} | SPACE: save | Q: quit | saved: {count}", (12, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            cv2.imshow("Cylinder dataset capture", display)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord(" "):
                stem = f"{args.class_name.lower()}_{time.strftime('%Y%m%d_%H%M%S')}_{time.time_ns() % 1_000_000:06d}"
                image_path = image_dir / f"{stem}.jpg"
                if not cv2.imwrite(str(image_path), frame):
                    raise RuntimeError(f"Could not save {image_path}")
                if args.full_frame_label:
                    (label_dir / f"{stem}.txt").write_text(f"{class_id} 0.5 0.5 1.0 1.0\n", encoding="utf-8")
                count += 1
                print(f"saved: {image_path}")
    finally:
        if args.camera_backend == "picamera2":
            camera.stop()
        else:
            camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
