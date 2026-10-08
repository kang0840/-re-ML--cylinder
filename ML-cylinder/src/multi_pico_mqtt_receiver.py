"""MQTT receiver for a fleet of Pico W sensor publishers on Raspberry Pi 5."""
from __future__ import annotations

import json
import logging
import os
import re
import signal
import threading
from dataclasses import dataclass

import paho.mqtt.client as mqtt

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"),
                    format="%(asctime)s %(levelname)s %(message)s")
LOG = logging.getLogger("multi-pico-mqtt")
TOPIC_RE = re.compile(r"^cylinder/([^/]+)/(sensor|status)$")


@dataclass
class PicoState:
    status: str = "OFF"


class PicoFleetReceiver:
    def __init__(self) -> None:
        self.states: dict[str, PicoState] = {}
        self.stop_event = threading.Event()
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                  client_id=os.getenv("PI5_MQTT_CLIENT_ID", "cylinder_pi5_receiver"),
                                  clean_session=False)
        username = os.getenv("MQTT_USERNAME")
        if username:
            self.client.username_pw_set(username, os.getenv("MQTT_PASSWORD"))
        self.client.reconnect_delay_set(min_delay=1, max_delay=60)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message

    def on_connect(self, client, _userdata, _flags, reason_code, _properties):
        if reason_code != 0:
            LOG.error("broker rejected Pi 5 client: %s", reason_code)
            return
        for topic in ("cylinder/+/sensor", "cylinder/+/status"):
            result, _mid = client.subscribe(topic, qos=1)
            LOG.info("subscribed %s: result=%s", topic, result)

    def on_disconnect(self, _client, _userdata, _flags, reason_code, _properties):
        LOG.warning("MQTT disconnected: %s; automatic reconnect pending", reason_code)

    def on_message(self, _client, _userdata, message):
        match = TOPIC_RE.fullmatch(message.topic)
        if not match:
            LOG.warning("ignored unexpected topic: %s", message.topic)
            return
        topic_device, kind = match.groups()
        try:
            payload = json.loads(message.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            LOG.warning("invalid JSON from %s: %s", message.topic, error)
            return
        if payload.get("device_id") != topic_device:
            LOG.error("identity mismatch topic=%s payload=%r; ignored", topic_device,
                      payload.get("device_id"))
            return
        state = self.states.setdefault(topic_device, PicoState())
        if kind == "status":
            state.status = "ON" if payload.get("status") == "online" else "OFF"
            LOG.info("%s : %s", topic_device, state.status)
        else:
            LOG.info("sensor from %s: %s", topic_device, payload)
            # Insert database/storage/analysis handoff here.

    def run(self):
        host = os.getenv("MQTT_BROKER_HOST", "127.0.0.1")
        port = int(os.getenv("MQTT_BROKER_PORT", "1883"))
        LOG.info("connecting Pi 5 receiver to %s:%s", host, port)
        self.client.connect_async(host, port, keepalive=60)
        self.client.loop_start()
        self.stop_event.wait()
        self.client.disconnect()
        self.client.loop_stop()


if __name__ == "__main__":
    receiver = PicoFleetReceiver()
    signal.signal(signal.SIGTERM, lambda *_: receiver.stop_event.set())
    signal.signal(signal.SIGINT, lambda *_: receiver.stop_event.set())
    receiver.run()
