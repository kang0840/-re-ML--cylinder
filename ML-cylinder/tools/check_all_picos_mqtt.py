"""Check whether pico01 through pico06 respond independently over MQTT.

Run on the Raspberry Pi (where the MQTT broker is reachable):
    set -a; source /etc/acoustic/analytics.env; set +a
    python3 tools/check_all_picos_mqtt.py

The script sends one targeted diagnostic token to every Pico.  A Pico is OK
only when it returns a raw packet with its own device_id and this run's token.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from pathlib import Path

import paho.mqtt.client as mqtt


DEVICES = tuple(f"pico{number:02d}" for number in range(1, 7))


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description="MQTT Pico 01~06 connection check")
    parser.add_argument("--env", default="/etc/acoustic/analytics.env")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--timeout", type=float, default=15,
                        help="seconds to wait after publishing all diagnostic tokens")
    args = parser.parse_args()
    config = {**load_env(Path(args.env)), **os.environ}
    host = args.host or config.get("MQTT_BROKER_HOST", "localhost")
    port = args.port or int(config.get("MQTT_BROKER_PORT", "1883"))
    username = config.get("MQTT_USERNAME", "")
    password = config.get("MQTT_PASSWORD", "")
    password_file = Path("/etc/mosquitto/passwd")
    print("=== Pi MQTT configuration ===")
    print(f"Broker: {host}:{port}")
    print(f"Pi MQTT username: {username or '(not configured)'}")
    print(f"Pi MQTT password: {'configured' if password else 'NOT configured'}")
    if password_file.exists():
        users = [line.partition(":")[0] for line in password_file.read_text(encoding="utf-8").splitlines()]
        print("Broker Pico IDs:", ", ".join(user for user in users if user in DEVICES) or "none")
        print("Pi username registered:", "YES" if username in users else "NO")
    print("\n=== Pico 01~06 response test ===")
    cycle_id = f"diagnostic-{uuid.uuid4().hex[:12]}"
    received: dict[str, dict] = {}
    connected = False

    def on_connect(client, userdata, flags, reason_code, properties):
        nonlocal connected
        if reason_code != 0:
            print(f"MQTT connection failed: {reason_code}")
            return
        connected = True
        client.subscribe("smartCylinder/+/inmp441/raw", qos=1)
        client.subscribe("smartCylinder/+/status", qos=1)

    def on_message(client, userdata, message):
        try:
            payload = json.loads(message.payload)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        device_id = str(payload.get("device_id", ""))
        # A status topic is informative; a matching raw response proves the
        # Pico received this particular diagnostic token.
        if device_id in DEVICES and payload.get("cycle_id") == cycle_id:
            received[device_id] = {
                "topic": message.topic,
                "sequence": payload.get("sequence", "-"),
                "boot_id": payload.get("boot_id", "-"),
            }

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"pico-registration-check-{uuid.uuid4().hex[:8]}",
        clean_session=True,
    )
    if username:
        client.username_pw_set(username, password)
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(host, port, keepalive=30)
        client.loop_start()
        deadline = time.monotonic() + 8
        while not connected and time.monotonic() < deadline:
            time.sleep(0.1)
        if not connected:
            print(f"Could not connect to MQTT broker at {host}:{port}")
            return 2

        for device_id in DEVICES:
            token = {
                "device_id": device_id,
                "cycle_id": cycle_id,
                "timeout_seconds": args.timeout,
                "purpose": "registration_check",
            }
            client.publish(f"smartCylinder/control/{device_id}/token", json.dumps(token), qos=1)

        deadline = time.monotonic() + args.timeout
        while time.monotonic() < deadline and len(received) < len(DEVICES):
            time.sleep(0.1)
    finally:
        client.loop_stop()
        client.disconnect()

    print(f"MQTT broker: {host}:{port}  cycle: {cycle_id}")
    print("device   result  details")
    print("-------  ------  ----------------------------------------")
    for device_id in DEVICES:
        item = received.get(device_id)
        if item:
            print(f"{device_id:<7}  OK      sequence={item['sequence']} boot={item['boot_id']}")
        else:
            print(f"{device_id:<7}  FAIL    no response; check DEVICE_ID, MQTT_CLIENT_ID, ID/PW, and Wi-Fi")

    missing = [device for device in DEVICES if device not in received]
    if missing:
        print("\nOnly the listed OK IDs answered. If just pico01 is OK, the other boards are likely still configured as pico01.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
