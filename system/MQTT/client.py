"""Pi MQTT client connection and re-subscription coordination."""


class PiMqttClient:
    """Connect an injected paho client to the local Mosquitto broker."""

    def __init__(
        self,
        mqtt_client,
        topic="smart-cylinder/+/sensor",
        subscriber=None,
        broker_host="127.0.0.1",
        broker_port=1883,
        keepalive=60,
        username="pi-subscriber",
        password=None,
    ):
        self._mqtt_client = mqtt_client
        self._topic = topic
        self._subscriber = subscriber
        self._broker_host = broker_host
        self._broker_port = broker_port
        self._keepalive = keepalive
        self._username = username
        self._password = password

    def connect_and_subscribe(self):
        """Set optional authentication before connecting and subscribing at QoS 1."""
        if self._username is not None and self._password is not None:
            self._mqtt_client.username_pw_set(self._username, self._password)
        self._mqtt_client.on_message = self._paho_on_message
        self._mqtt_client.connect(
            self._broker_host,
            self._broker_port,
            self._keepalive,
        )
        self._mqtt_client.subscribe(self._topic, qos=1)

    def on_reconnect(self):
        """Restore the same topic subscription after MQTT reconnection."""
        self._mqtt_client.subscribe(self._topic, qos=1)

    def on_message(self, raw_payload):
        """Forward raw broker payloads to the parser and duplicate gate."""
        if self._subscriber is None:
            raise RuntimeError("a subscriber is required to process broker messages")
        if hasattr(self._subscriber, "enqueue_message"):
            return self._subscriber.enqueue_message(raw_payload)
        return self._subscriber.handle_message(raw_payload)

    def _paho_on_message(self, _client, _userdata, message):
        """Adapt paho's broker callback shape to the project subscriber."""
        if self._subscriber is not None and hasattr(
            self._subscriber, "enqueue_message"
        ):
            return self._subscriber.enqueue_message(message.payload, message.topic)
        return self.on_message(message.payload)
