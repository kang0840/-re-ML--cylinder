#!/usr/bin/env python3
"""Read-only, compact MQTT monitor for the Raspberry Pi sensor network.

This program never writes to the database or invokes ML.  It only subscribes
to Pico status and raw MQTT topics and prints a short, readable summary.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

import paho.mqtt.client as mqtt


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def short_time(value: object) -> str:
    try:
        return datetime.fromtimestamp(float(value)).strftime("%H:%M:%S")
    except (TypeError, ValueError, OSError, OverflowError):
        return "-"


def print_status(topic: str, payload: dict[str, object]) -> None:
    device = str(payload.get("device_id") or topic.split("/")[1])
    state = str(payload.get("status", "unknown")).upper()
    rows.setdefault(device, {})["status"] = state
    rows[device]["updated"] = time.strftime("%H:%M:%S")
    render()


def print_raw(topic: str, payload: dict[str, object]) -> None:
    device = str(payload.get("device_id") or topic.split("/")[1])
    sensor = str(payload.get("sensor_type") or topic.split("/")[2])
    samples = payload.get("samples")
    if not isinstance(samples, list) or not samples:
        rows.setdefault(device, {})["note"] = "invalid frame"
        render()
        return

    try:
        numbers = [float(sample) for sample in samples]
    except (TypeError, ValueError):
        rows.setdefault(device, {})["note"] = "invalid samples"
        render()
        return

    rms = math.sqrt(sum(sample * sample for sample in numbers) / len(numbers))
    sequence = payload.get("sequence", "?")
    captured = short_time(payload.get("timestamp"))
    quality = str(payload.get("timestamp_quality", "unknown"))
    dropped = payload.get("dropped_frames", 0)
    rows.setdefault(device, {}).update(
        status=rows.get(device, {}).get("status", "ONLINE"),
        captured=captured,
        sensor=sensor,
        sequence=sequence,
        count=len(numbers),
        minimum=min(numbers),
        maximum=max(numbers),
        rms=rms,
        quality=quality,
        dropped=dropped,
        updated=time.strftime("%H:%M:%S"),
        note="",
    )
    render()


rows: dict[str, dict[str, object]] = {device: {"status": "WAITING"} for device in (f"pico{i:02d}" for i in range(1, 7))}


def render() -> None:
    """Redraw a fixed six-Pico table instead of endlessly appending lines."""
    lines = [
        "PICO SENSOR MONITOR  (read-only; Ctrl+C to exit)",
        "Pico    Status    Time      Sensor      Seq       Min     Max     RMS    Note",
        "-" * 82,
    ]
    for device in sorted(rows):
        row = rows[device]
        status = str(row.get("status", "WAITING"))
        if "sequence" not in row:
            lines.append(f"{device:<7} {status:<9} {'-':<9} {'-':<11} {'-':<9} {'-':>7} {'-':>7} {'-':>7} {row.get('note', '')}")
            continue
        lines.append(
            f"{device:<7} {status:<9} {str(row.get('captured', '-')):<9} "
            f"{str(row.get('sensor', '-')):<11} {str(row.get('sequence', '-')):<9} "
            f"{float(row.get('minimum', 0)):>7.0f} {float(row.get('maximum', 0)):>7.0f} "
            f"{float(row.get('rms', 0)):>7.0f} {row.get('quality', '')}"
        )
    print("\033[2J\033[H" + "\n".join(lines), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compact, read-only Pico MQTT monitor")
    parser.add_argument("--env", default="/opt/smart-cylinder-pi5/.env")
    args = parser.parse_args()
    env = {**load_env(Path(args.env)), **os.environ}
    host = env.get("MQTT_BROKER_HOST", "localhost")
    port = int(env.get("MQTT_BROKER_PORT", "1883"))
    username = env.get("MQTT_USERNAME")
    password = env.get("MQTT_PASSWORD")
    if not username or not password:
        print("MQTT_USERNAME or MQTT_PASSWORD is missing.", file=sys.stderr)
        return 2

    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"sensor-monitor-{os.getpid()}")
    except AttributeError:
        client = mqtt.Client(client_id=f"sensor-monitor-{os.getpid()}")
    client.username_pw_set(username, password)

    def on_connect(client: mqtt.Client, _userdata: object, _flags: object, reason_code: object, _properties: object = None) -> None:
        if int(reason_code) != 0:
            print(f"MQTT connection failed: {reason_code}", file=sys.stderr, flush=True)
            return
        client.subscribe("smartCylinder/+/status", qos=1)
        client.subscribe("smartCylinder/+/+/raw", qos=1)
        print(f"Connected to MQTT at {host}:{port}. Waiting for Pico messages...", flush=True)

    def on_message(_client: mqtt.Client, _userdata: object, message: mqtt.MQTTMessage) -> None:
        try:
            payload = json.loads(message.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            print(f"[{message.topic}] invalid JSON", flush=True)
            return
        if message.topic.endswith("/status"):
            print_status(message.topic, payload)
        else:
            print_raw(message.topic, payload)

    client.on_connect = on_connect
    client.on_message = on_message
    signal.signal(signal.SIGINT, lambda *_args: client.disconnect())
    render()
    client.connect(host, port, keepalive=30)
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
