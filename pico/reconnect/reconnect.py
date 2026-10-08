"""Reconnect coordination that preserves Pico boot-session state."""


class ReconnectionCoordinator:
    """Reconnect transport only; session and sequence ownership stay external."""

    def __init__(self, identity_state, reconnect_wifi, reconnect_mqtt):
        self.identity_state = identity_state
        self._reconnect_wifi = reconnect_wifi
        self._reconnect_mqtt = reconnect_mqtt

    def restore_connection(self):
        """Restore Wi-Fi then MQTT without recreating identity_state."""
        self._reconnect_wifi()
        self._reconnect_mqtt()
        return self.identity_state.session_id
