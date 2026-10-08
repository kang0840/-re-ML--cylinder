"""Read-only MQTT username/password verification for Raspberry Pi.

The broker stores password hashes, so checking its password file alone cannot
prove that a supplied password is correct.  This script verifies the pair by
opening an MQTT connection and immediately disconnecting.
"""
from __future__ import annotations

import argparse
import os
import sys
import threading

import paho.mqtt.client as mqtt


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify MQTT credentials without publishing data")
    parser.add_argument("--host", default=os.getenv("MQTT_BROKER_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MQTT_BROKER_PORT", "1883")))
    parser.add_argument("--username", default=os.getenv("MQTT_USERNAME"))
    parser.add_argument("--password", default=os.getenv("MQTT_PASSWORD"))
    parser.add_argument("--timeout", type=float, default=8)
    args = parser.parse_args()

    if not args.username or args.password is None:
        print("FAIL: MQTT username/password is missing. Use arguments or environment variables.")
        return 2

    result: dict[str, object] = {}
    done = threading.Event()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id=f"credential-check-{os.getpid()}", clean_session=True)
    client.username_pw_set(args.username, args.password)

    def on_connect(_client, _userdata, _flags, reason_code, _properties):
        result["reason_code"] = reason_code
        done.set()

    client.on_connect = on_connect
    try:
        print(f"Checking MQTT broker {args.host}:{args.port} as username={args.username!r} ...")
        client.connect_async(args.host, args.port, keepalive=15)
        client.loop_start()
        if not done.wait(args.timeout):
            print("FAIL: no broker response (check Pi network, broker address, and port).")
            return 1
        if result["reason_code"] != 0:
            print(f"FAIL: broker rejected the credentials: {result['reason_code']}")
            return 1
        print("OK: MQTT username and password were accepted by the broker.")
        return 0
    except OSError as error:
        print(f"FAIL: could not reach the broker: {error}")
        return 1
    finally:
        client.disconnect()
        client.loop_stop()


if __name__ == "__main__":
    raise SystemExit(main())
