"""MQTT message dispatch with session-aware duplicate classification."""

from .message_parser import parse_payload


class DuplicateTracker:
    """Keep the latest received payload for each QoS 1 message identity."""

    def __init__(self):
        self._messages = {}

    def record(self, payload):
        """Record a message and report whether the identity was already seen."""
        key = payload["duplicate_key"]
        is_duplicate = key in self._messages
        self._messages[key] = payload
        return is_duplicate


class MqttSubscriber:
    """Parse received payloads before forwarding only new messages downstream."""

    def __init__(self, on_message, duplicate_tracker=None):
        self._on_message = on_message
        self._duplicate_tracker = duplicate_tracker or DuplicateTracker()

    def handle_message(self, raw_payload):
        payload = parse_payload(raw_payload)
        is_duplicate = self._duplicate_tracker.record(payload)
        if not is_duplicate:
            self._on_message(payload, is_duplicate)
        return payload, is_duplicate
