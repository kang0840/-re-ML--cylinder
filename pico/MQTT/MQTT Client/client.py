"""Pico QoS 1 publishing through the Raspberry Pi Mosquitto broker."""

import json

try:
    from umqtt.simple import MQTTClient as _MicroPythonMqttClient
except ImportError:
    _MicroPythonMqttClient = None


ALLOWED_PICO_CLIENT_IDS = (
    "pico01",
    "pico02",
    "pico03",
    "pico04",
    "pico05",
    "pico06",
)

CLIENT_CYLINDER_MAP = {
    "pico01": "cylinder_01",
    "pico02": "cylinder_02",
    "pico03": "cylinder_03",
    "pico04": "cylinder_04",
    "pico05": "cylinder_05",
    "pico06": "cylinder_06",
}


def sensor_topic(cylinder_id):
    """Return the final sensor topic for one mapped cylinder."""
    return "smart-cylinder/%s/sensor" % cylinder_id


def status_topic(cylinder_id):
    """Return the retained online/offline status topic for one cylinder."""
    return "cylinder/status/%s" % cylinder_id


def _mqtt_bytes(value):
    if value is None or isinstance(value, bytes):
        return value
    return value.encode("utf-8")


class PicoMqttPublisher:
    """Publish new messages once and retry their exact serialized payloads."""

    def __init__(
        self,
        topic,
        identity_state,
        payload_builder,
        broker_host,
        broker_port=1883,
        keepalive=60,
        client_id=None,
        username=None,
        password=None,
        mqtt_client=None,
        mqtt_client_factory=None,
        timestamp_provider=None,
    ):
        if client_id not in ALLOWED_PICO_CLIENT_IDS:
            raise ValueError("client_id must be one of pico01 through pico06")
        if username is None:
            username = client_id
        elif username != client_id:
            raise ValueError("username must match client_id")
        if broker_host in ("localhost", "127.0.0.1"):
            raise ValueError("Pico broker_host must be the Raspberry Pi LAN address")
        if not isinstance(broker_host, str) or not broker_host:
            raise ValueError("broker_host must be a non-empty Raspberry Pi LAN address")
        expected_cylinder_id = CLIENT_CYLINDER_MAP[client_id]
        if topic != sensor_topic(expected_cylinder_id):
            raise ValueError("topic must match the client_id cylinder mapping")
        self._topic = topic
        self._identity_state = identity_state
        self._payload_builder = payload_builder
        self._broker_host = broker_host
        self._broker_port = broker_port
        self._keepalive = keepalive
        self._client_id = client_id
        self._cylinder_id = expected_cylinder_id
        self._username = username
        self._password = password
        self._mqtt_client = mqtt_client
        self._mqtt_client_factory = mqtt_client_factory
        self._timestamp_provider = timestamp_provider
        self._pending_payloads = {}

    def connect(self):
        """Connect the Pico publisher to the Raspberry Pi Mosquitto broker."""
        if self._mqtt_client is None:
            self._mqtt_client = self._create_client()
        self._mqtt_client.connect()
        self._mqtt_client.publish(
            _mqtt_bytes(status_topic(self._cylinder_id)),
            b"ok",
            retain=True,
            qos=1,
        )

    def reconnect(self):
        """Recreate the transport while preserving session and pending payloads."""
        self._close_transport()
        self._mqtt_client = self._create_client()
        self.connect()

    def disconnect(self):
        """Publish a graceful offline state and close the MQTT transport."""
        if self._mqtt_client is None:
            return
        try:
            self._mqtt_client.publish(
                _mqtt_bytes(status_topic(self._cylinder_id)),
                b"failed",
                retain=True,
                qos=1,
            )
        except Exception:
            pass
        finally:
            self._close_transport()

    def publish_new(self, cylinder_id, timestamp, sph0645, inmp441):
        """Create a new logical message and publish it at QoS 1."""
        if not getattr(self._timestamp_provider, "time_synced", False):
            raise RuntimeError("publish requires successful NTP synchronization")
        if cylinder_id != self._cylinder_id:
            raise ValueError("cylinder_id must match the client_id mapping")
        sequence_id = self._identity_state.next_sequence_id()
        payload = self._payload_builder(
            cylinder_id,
            self._identity_state.session_id,
            sequence_id,
            timestamp,
            sph0645,
            inmp441,
        )
        if payload.get("cylinder_id") != self._cylinder_id:
            raise ValueError("payload cylinder_id must match the publish topic")
        encoded_payload = json.dumps(payload)
        self._pending_payloads[sequence_id] = encoded_payload
        try:
            self._publish(encoded_payload)
        except Exception:
            raise
        else:
            self.mark_delivered(sequence_id)
        return sequence_id

    def republish(self, sequence_id):
        """Retry an existing logical message without allocating a new ID."""
        encoded_payload = self._pending_payloads[sequence_id]
        try:
            self._publish(encoded_payload)
        except Exception:
            raise
        else:
            self.mark_delivered(sequence_id)

    def republish_pending(self):
        """Retry stored QoS 1 payloads in their original sequence order."""
        for sequence_id in sorted(tuple(self._pending_payloads)):
            self.republish(sequence_id)

    def mark_delivered(self, sequence_id):
        """Release a payload only after the MQTT client confirms completion."""
        self._pending_payloads.pop(sequence_id, None)

    def _publish(self, encoded_payload):
        if self._mqtt_client is None:
            raise RuntimeError("connect must be called before publish")
        self._mqtt_client.publish(
            _mqtt_bytes(self._topic), _mqtt_bytes(encoded_payload), qos=1
        )

    def _create_client(self):
        factory = self._mqtt_client_factory or _MicroPythonMqttClient
        if factory is None:
            raise RuntimeError("umqtt.simple.MQTTClient is unavailable")
        if self._client_id is None:
            raise ValueError("client_id is required to create MQTTClient")
        mqtt_client = factory(
            _mqtt_bytes(self._client_id),
            self._broker_host,
            port=self._broker_port,
            user=_mqtt_bytes(self._username),
            password=_mqtt_bytes(self._password),
            keepalive=self._keepalive,
        )
        mqtt_client.set_last_will(
            _mqtt_bytes(status_topic(self._cylinder_id)),
            b"failed",
            retain=True,
            qos=1,
        )
        return mqtt_client

    def _close_transport(self):
        mqtt_client = self._mqtt_client
        self._mqtt_client = None
        if mqtt_client is None:
            return
        try:
            mqtt_client.disconnect()
        except Exception:
            pass
