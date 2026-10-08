"""Pico boot-session and MQTT sequence identity helpers."""


def generate_uuid_v4(random_bytes):
    """Create a UUID v4 string from a platform-provided random-byte function.

    Pico W runtime code must provide and hardware-validate ``random_bytes``.
    This module intentionally does not select a MicroPython random API.
    """
    raw = bytearray(random_bytes(16))
    if len(raw) != 16:
        raise ValueError("random_bytes must return 16 bytes")
    raw[6] = (raw[6] & 0x0F) | 0x40
    raw[8] = (raw[8] & 0x3F) | 0x80
    text = "".join("%02x" % value for value in raw)
    return "%s-%s-%s-%s-%s" % (
        text[0:8],
        text[8:12],
        text[12:16],
        text[16:20],
        text[20:32],
    )


class SessionSequenceState:
    """Keep one Pico boot session ID and increasing MQTT message IDs."""

    def __init__(self, random_bytes):
        self.session_id = generate_uuid_v4(random_bytes)
        self._sequence_id = 0

    def next_sequence_id(self):
        """Reserve the next identity for one new logical MQTT message."""
        self._sequence_id += 1
        return self._sequence_id

    def current_sequence_id(self):
        """Return the most recently reserved sequence ID, if any."""
        return self._sequence_id
