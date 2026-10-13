"""Manual A-only MQTT transport; reusable by a future YOLO caller."""

import os
import threading
import uuid
from dataclasses import dataclass

TOPIC = "smart-cylinder/yolo/test"


class SenderError(Exception):
    """Only sanitized, predefined errors may be exposed to the operator."""


@dataclass(frozen=True, repr=False)
class BrokerSettings:
    host: str
    username: str
    password: str
    port: int = 1883

    @classmethod
    def from_environment(cls):
        values = [os.environ.get(name, "") for name in (
            "MQTT_BROKER_HOST", "MQTT_USERNAME", "MQTT_PASSWORD"
        )]
        if not all(values):
            raise SenderError("CONFIG_REQUIRED")
        host, username, password = values
        if host.strip().lower() in {"localhost", "127.0.0.1", "::1"}:
            raise SenderError("PI_BROKER_HOST_REQUIRED")
        try:
            port = int(os.environ.get("MQTT_BROKER_PORT", "1883"))
        except ValueError:
            raise SenderError("INVALID_PORT") from None
        if not 1 <= port <= 65535:
            raise SenderError("INVALID_PORT")
        return cls(host.strip(), username, password, port)


def _new_client():
    import paho.mqtt.client as mqtt

    return mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id="pc-yolo-test-" + uuid.uuid4().hex,
        reconnect_on_failure=False,
    )


def publish_detection(label, settings, *, timeout=10, client_factory=None):
    """Publish exactly A and await PUBACK. A new connection is used each call.

    No application retry occurs: a missing ACK can mean delivery is uncertain.
    Broker acknowledgement does not confirm Data WorX display or PLC motion.
    """
    if label != "A":
        raise SenderError("ONLY_A_ALLOWED")
    ready = threading.Event()
    accepted = []
    disconnected = threading.Event()
    client = None

    def on_connect(_client, _userdata, _flags, reason_code, _properties):
        accepted.append(not reason_code.is_failure)
        ready.set()

    def on_disconnect(_client, _userdata, _flags, _reason, _properties):
        disconnected.set()

    try:
        client = (client_factory or _new_client)()
        client.on_connect = on_connect
        client.on_disconnect = on_disconnect
        client.username_pw_set(settings.username, settings.password)
        client.connect_timeout = timeout
        client.connect(settings.host, settings.port, keepalive=60)
        client.loop_start()
        if not ready.wait(timeout):
            raise SenderError("CONNECT_TIMEOUT")
        if not accepted[0]:
            raise SenderError("CONNECTION_REJECTED_CHECK_AUTH")
        if disconnected.is_set():
            raise SenderError("DISCONNECTED")
        info = client.publish(TOPIC, payload=b"A", qos=1, retain=False)
        if info.rc != 0:
            raise SenderError("PUBLISH_REJECTED")
        try:
            info.wait_for_publish(timeout=timeout)
        except Exception:
            raise SenderError("PUBACK_UNCONFIRMED_DELIVERY_UNKNOWN") from None
        if not info.is_published():
            raise SenderError("PUBACK_UNCONFIRMED_DELIVERY_UNKNOWN")
        return "PUBLISHED"
    except SenderError:
        raise
    except Exception:
        raise SenderError("MQTT_CONNECTION_OR_TRANSPORT_FAILED") from None
    finally:
        if client is not None:
            for cleanup in (client.disconnect, client.loop_stop):
                try:
                    cleanup()
                except Exception:
                    pass


def main(input_fn=input, output_fn=print, publisher=publish_detection):
    try:
        settings = BrokerSettings.from_environment()
    except SenderError as error:
        output_fn(f"FAILED: {error}")
        return 1
    output_fn(f"Topic: {TOPIC} | Payload: A | QoS: 1 | Retain: False")
    output_fn("A를 입력해 전송합니다. 종료: quit 또는 Ctrl+C")
    while True:
        try:
            label = input_fn("> ")
            if label == "quit":
                return 0
            if label != "A":
                output_fn("FAILED: ONLY_A_ALLOWED")
                continue
            output_fn(publisher(label, settings))
        except SenderError as error:
            output_fn(f"FAILED: {error}")
        except (EOFError, KeyboardInterrupt):
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
