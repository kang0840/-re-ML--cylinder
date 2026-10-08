"""Raspberry Pi 5 camera preview and YOLO object-detection MJPEG server.

Uses the CSI camera through Picamera2 by default.  A USB webcam can be used
with ``--camera-backend opencv``.  The browser page in public/ expects the
MJPEG feed at /stream.
"""

from __future__ import annotations

import argparse
import atexit
import json
import time
from threading import Lock
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

import cv2
import paho.mqtt.client as mqtt
from flask import Flask, Response, jsonify


class Camera:
    def __init__(self, backend: str, width: int, height: int, fps: int, device: int):
        self.backend = backend
        self.lock = Lock()
        self.picam2 = None
        self.capture = None
        if backend == "picamera2":
            from picamera2 import Picamera2

            self.picam2 = Picamera2()
            config = self.picam2.create_video_configuration(
                main={"size": (width, height), "format": "RGB888"},
                controls={"FrameRate": fps},
            )
            self.picam2.configure(config)
            self.picam2.start()
            time.sleep(1)  # Allow auto exposure to settle.
        else:
            self.capture = cv2.VideoCapture(device)
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            self.capture.set(cv2.CAP_PROP_FPS, fps)
            if not self.capture.isOpened():
                raise RuntimeError(f"USB camera /dev/video{device} could not be opened")

    def read(self):
        with self.lock:
            if self.picam2 is not None:
                # Picamera2 supplies RGB; OpenCV and YOLO expect BGR images.
                return cv2.cvtColor(self.picam2.capture_array(), cv2.COLOR_RGB2BGR)
            ok, frame = self.capture.read()
            if not ok:
                raise RuntimeError("Could not read a frame from the USB camera")
            return frame

    def close(self):
        if self.picam2 is not None:
            self.picam2.stop()
        if self.capture is not None:
            self.capture.release()


class DetectionPublisher:
    """Publish only when the classification changes, never once per frame."""

    def __init__(self, host: str, port: int, topic: str):
        self.topic = topic
        self.last_result = None
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.connect_async(host, port, keepalive=60)
        self.client.loop_start()

    def update(self, result: str | None):
        if result is not None and result != self.last_result:
            message = json.dumps({"result": result}, ensure_ascii=False)
            info = self.client.publish(self.topic, message, qos=1)
            if info.rc != mqtt.MQTT_ERR_SUCCESS:
                raise RuntimeError(f"MQTT publish failed with code {info.rc}")
        self.last_result = result

    def close(self):
        self.client.loop_stop()
        self.client.disconnect()


class ResultUploader:
    """Keep the newest annotated result locally and optionally upload it to Render."""

    def __init__(self, result_dir: str, upload_url: str | None, upload_key: str | None,
                 interval: float):
        self.directory = Path(result_dir)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.upload_url = upload_url
        self.upload_key = upload_key
        self.interval = interval
        self.last_written_at = 0.0

    def update(self, jpeg: bytes, result: str | None, labels: list[str]):
        now = time.time()
        if now - self.last_written_at < self.interval:
            return
        self.last_written_at = now
        captured_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
        (self.directory / "latest.jpg").write_bytes(jpeg)
        (self.directory / "latest.json").write_text(json.dumps({
            "captured_at": captured_at, "result": result, "labels": labels,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        if not (self.upload_url and self.upload_key):
            return
        request = Request(self.upload_url, data=jpeg, method="POST", headers={
            "Content-Type": "image/jpeg",
            "X-Camera-Key": self.upload_key,
            "X-Camera-Captured-At": captured_at,
            "X-Camera-Result": result or "",
            "X-Camera-Labels": ", ".join(labels),
        })
        try:
            with urlopen(request, timeout=5) as response:
                if response.status >= 300:
                    raise RuntimeError(f"Upload returned HTTP {response.status}")
        except (OSError, URLError, RuntimeError) as exc:
            print(f"Camera result upload failed: {exc}")


def normalise_label(label: str) -> str:
    return label.strip().upper().replace("-", "_").replace(" ", "_")


def classify(result, a_class: str, b_class: str) -> str | None:
    """Return A/B only for one valid cylinder; unknown or mixed boxes are defective."""
    if result.boxes is None or len(result.boxes) == 0:
        return None
    names = result.names
    labels = {normalise_label(names[int(class_id)]) for class_id in result.boxes.cls.tolist()}
    a_label, b_label = normalise_label(a_class), normalise_label(b_class)
    if labels == {a_label}:
        return "A_CYLINDER"
    if labels == {b_label}:
        return "B_CYLINDER"
    return "DEFECTIVE"


def create_app(camera: Camera, model_path: str | None, confidence: float,
               publisher: DetectionPublisher | None, uploader: ResultUploader,
               a_class: str, b_class: str):
    app = Flask(__name__)
    model = None
    if model_path:
        from ultralytics import YOLO

        model = YOLO(model_path)

    def annotated_frame():
        frame = camera.read()
        classification = None
        labels = []
        if model is not None:
            # imgsz 640 is a practical starting point for Pi 5. Lower it for FPS.
            result = model(frame, imgsz=640, conf=confidence, verbose=False)[0]
            classification = classify(result, a_class, b_class)
            if result.boxes is not None:
                labels = [normalise_label(result.names[int(class_id)]) for class_id in result.boxes.cls.tolist()]
            frame = result.plot()
        if publisher is not None:
            publisher.update(classification)
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(frame, now, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                    (0, 255, 0), 2, cv2.LINE_AA)
        return frame, classification, labels

    def generate():
        while True:
            try:
                frame, classification, labels = annotated_frame()
                ok, encoded = cv2.imencode(".jpg", frame,
                                           [cv2.IMWRITE_JPEG_QUALITY, 80])
                if not ok:
                    continue
                uploader.update(encoded.tobytes(), classification, labels)
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" +
                       encoded.tobytes() + b"\r\n")
            except Exception as exc:
                app.logger.exception("Frame processing failed: %s", exc)
                time.sleep(0.5)

    @app.get("/stream")
    def stream():
        return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")

    @app.get("/health")
    def health():
        return jsonify(ok=True, yolo_enabled=model is not None)

    return app


def parse_args():
    parser = argparse.ArgumentParser(description="Pi 5 Picamera2 + YOLO MJPEG server")
    parser.add_argument("--model", default="yolo11n.pt", help="YOLO .pt model; use 'none' for camera-only test")
    parser.add_argument("--camera-backend", choices=("picamera2", "opencv"), default="picamera2")
    parser.add_argument("--device", type=int, default=0, help="USB /dev/video index (opencv backend)")
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fps", type=int, default=20)
    parser.add_argument("--confidence", type=float, default=0.4)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--mqtt-host", help="MQTT broker hostname or IP; omit to disable MQTT")
    parser.add_argument("--mqtt-port", type=int, default=1883)
    parser.add_argument("--mqtt-topic", default="smartCylinder/yolo/result")
    parser.add_argument("--result-dir", default="outputs/camera",
                        help="directory for latest.jpg and latest.json on the Raspberry Pi")
    parser.add_argument("--upload-url", help="Render /api/camera/frame URL; omit for Pi-only use")
    parser.add_argument("--upload-key", help="CAMERA_UPLOAD_KEY configured on Render")
    parser.add_argument("--upload-interval", type=float, default=1.0,
                        help="seconds between result-file writes and uploads")
    parser.add_argument("--a-class", default="A_CYLINDER",
                        help="class name for a correct A cylinder in the YOLO model")
    parser.add_argument("--b-class", default="B_CYLINDER",
                        help="class name for a correct B cylinder in the YOLO model")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    camera = Camera(args.camera_backend, args.width, args.height, args.fps, args.device)
    atexit.register(camera.close)
    path = None if args.model.lower() == "none" else args.model
    publisher = None
    if args.mqtt_host:
        publisher = DetectionPublisher(args.mqtt_host, args.mqtt_port, args.mqtt_topic)
        atexit.register(publisher.close)
    uploader = ResultUploader(args.result_dir, args.upload_url, args.upload_key, args.upload_interval)
    create_app(camera, path, args.confidence, publisher, uploader, args.a_class, args.b_class).run(
        host=args.host, port=args.port, threaded=False, debug=False
    )
