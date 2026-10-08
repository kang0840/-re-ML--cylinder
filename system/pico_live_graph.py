"""Serve a non-persistent Pico 01 MQTT feature graph on Raspberry Pi 5."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import threading
from collections import deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from system.ML.Condition.analysis import CycleFeatureExtractor
from system.MQTT.client import PiMqttClient
from system.MQTT.subscriber import MqttSubscriber

CYLINDER_ID = "cylinder_01"
SENSOR_TOPIC = "smart-cylinder/cylinder_01/sensor"
MQTT_CLIENT_ID = "pi-subscriber"
DEFAULT_HTTP_PORT = 8080
DEFAULT_MAX_POINTS = 120
MONITOR_LOCK_PATH = "/tmp/smart-cylinder-pico-monitor.lock"
FRONTEND_PATH = Path(__file__).resolve().parent / "Frontend" / "pico01_live.html"


class LiveGraphState:
    """Keep a bounded, thread-safe history of Pico 01 feature summaries."""

    def __init__(self, max_points: int = DEFAULT_MAX_POINTS) -> None:
        self._points: deque[dict[str, Any]] = deque(maxlen=max_points)
        self._lock = threading.Lock()
        self._mqtt_connected = False
        self._last_error: str | None = None
        self._extractor = CycleFeatureExtractor()

    def set_mqtt_connected(self, connected: bool) -> None:
        with self._lock:
            self._mqtt_connected = connected

    def record_error(self, error: Exception) -> None:
        with self._lock:
            self._last_error = "%s: %s" % (type(error).__name__, error)

    def handle_message(self, payload: dict[str, Any], is_duplicate: bool) -> None:
        """Calculate display-only features from one approved MQTT message."""
        if is_duplicate or payload["cylinder_id"] != CYLINDER_ID:
            return
        features = self._extractor.extract(
            payload["sph0645"]["samples"],
            payload["inmp441"]["samples"],
        )
        point = {
            "cylinder_id": payload["cylinder_id"],
            "session_id": payload["session_id"],
            "sequence_id": payload["sequence_id"],
            "measured_at": payload["timestamp"],
            "received_at": datetime.now(timezone.utc).isoformat(),
            "sph0645_rms": features["sph0645_rms"],
            "sph0645_peak": features["sph0645_peak"],
            "inmp441_rms": features["inmp441_rms"],
            "inmp441_peak": features["inmp441_peak"],
        }
        with self._lock:
            self._points.append(point)
            self._last_error = None

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            points = list(self._points)
            return {
                "cylinder_id": CYLINDER_ID,
                "mqtt_connected": self._mqtt_connected,
                "last_error": self._last_error,
                "latest": points[-1] if points else None,
                "points": points,
            }


def _create_handler(state: LiveGraphState, frontend: bytes):
    class LiveGraphHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            path = urlparse(self.path).path
            if path in ("/", "/pico01_live.html"):
                self._send_bytes("text/html; charset=utf-8", frontend)
                return
            if path == "/api/live":
                body = json.dumps(
                    state.snapshot(),
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8")
                self._send_bytes("application/json; charset=utf-8", body)
                return
            if path == "/health":
                self._send_bytes(
                    "application/json; charset=utf-8",
                    b'{"status":"ok"}',
                )
                return
            self.send_error(404)

        def log_message(self, message: str, *args: Any) -> None:
            print("[HTTP] " + (message % args))

        def _send_bytes(self, content_type: str, body: bytes) -> None:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    return LiveGraphHandler


def _create_paho_client(client_id: str):
    try:
        import paho.mqtt.client as mqtt
    except ImportError as error:
        raise RuntimeError("paho-mqtt is required") from error
    try:
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id=client_id)
    except AttributeError:
        return mqtt.Client(client_id=client_id)


def _acquire_monitor_lock():
    try:
        import fcntl
    except ImportError:
        return None
    handle = open(MONITOR_LOCK_PATH, "w", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as error:
        handle.close()
        raise RuntimeError(
            "Smart Cylinder Pico Monitor is already running; stop it first"
        ) from error
    return handle


def _required_password(cli_password: str | None) -> str:
    password = cli_password or os.environ.get("PICO_MONITOR_MQTT_PASSWORD")
    if password:
        return password
    password = getpass.getpass("pi-subscriber MQTT password: ")
    if not password:
        raise RuntimeError("MQTT password is required")
    return password


def run(args: argparse.Namespace) -> None:
    """Start the local MQTT subscriber and same-origin HTTP graph server."""
    if not FRONTEND_PATH.is_file():
        raise FileNotFoundError("Pico 01 live graph HTML was not found")
    monitor_lock = _acquire_monitor_lock()
    frontend = FRONTEND_PATH.read_bytes()
    state = LiveGraphState(max_points=args.max_points)
    subscriber = MqttSubscriber(state.handle_message)
    mqtt_client = _create_paho_client(MQTT_CLIENT_ID)
    mqtt_client.reconnect_delay_set(min_delay=1, max_delay=30)
    pi_client = PiMqttClient(
        mqtt_client,
        topic=SENSOR_TOPIC,
        subscriber=subscriber,
        broker_host=args.broker_host,
        broker_port=args.broker_port,
        keepalive=args.keepalive,
        username=args.username,
        password=_required_password(args.password),
    )

    def on_connect(_client, _userdata, _flags, reason_code):
        connected = int(reason_code) == 0
        state.set_mqtt_connected(connected)
        if connected:
            pi_client.on_reconnect()
            print("[MQTT] subscribed to %s" % SENSOR_TOPIC)
        else:
            state.record_error(RuntimeError("MQTT CONNACK %s" % reason_code))

    def on_disconnect(_client, _userdata, reason_code):
        state.set_mqtt_connected(False)
        if int(reason_code) != 0:
            state.record_error(RuntimeError("MQTT disconnected %s" % reason_code))

    def on_message(_client, _userdata, message):
        try:
            pi_client.on_message(message.payload)
        except Exception as error:
            state.record_error(error)
            print("[MQTT] message rejected: %s: %s" % (type(error).__name__, error))

    mqtt_client.on_connect = on_connect
    mqtt_client.on_disconnect = on_disconnect
    pi_client.connect_and_subscribe()
    mqtt_client.on_message = on_message
    mqtt_client.loop_start()

    server = ThreadingHTTPServer(
        (args.bind, args.http_port),
        _create_handler(state, frontend),
    )
    print("Pico 01 live graph: http://%s:%d" % (args.display_host, args.http_port))
    print("No sensor data is written to Supabase or any local database.")
    try:
        server.serve_forever(poll_interval=0.25)
    finally:
        server.shutdown()
        server.server_close()
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        if monitor_lock is not None:
            monitor_lock.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Pico 01 local live graph")
    parser.add_argument("--broker-host", default="127.0.0.1")
    parser.add_argument("--broker-port", type=int, default=1883)
    parser.add_argument("--keepalive", type=int, default=60)
    parser.add_argument("--username", default="pi-subscriber")
    parser.add_argument("--password", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--display-host", default="192.168.137.99")
    parser.add_argument("--http-port", type=int, default=DEFAULT_HTTP_PORT)
    parser.add_argument("--max-points", type=int, default=DEFAULT_MAX_POINTS)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.max_points < 2:
        raise SystemExit("--max-points must be at least 2")
    if not 1 <= args.http_port <= 65535:
        raise SystemExit("--http-port must be between 1 and 65535")
    run(args)


if __name__ == "__main__":
    main()
