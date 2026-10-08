"""Pico W single-SSID Wi-Fi connection management."""

try:
    import network as _network
except ImportError:
    _network = None

try:
    import time as _time
except ImportError:
    _time = None


CONNECTED = "CONNECTED"
FAILED = "FAILED"


class WiFiConnection:
    """Connect only to the caller-provided SSID and retain that configuration."""

    def __init__(
        self,
        ssid,
        password,
        timeout_seconds=15,
        wlan=None,
        network_module=None,
        time_module=None,
    ):
        self._ssid = ssid
        self._password = password
        self._timeout_seconds = timeout_seconds
        self._wlan = wlan
        self._network_module = network_module or _network
        self._time_module = time_module or _time

    def connect(self):
        """Connect to the configured SSID, returning CONNECTED or FAILED."""
        wlan = self._get_wlan()
        wlan.active(True)
        if wlan.isconnected():
            return CONNECTED
        try:
            wlan.connect(self._ssid, self._password)
        except Exception:
            return FAILED

        started_at = self._now()
        while not wlan.isconnected():
            if self._now() - started_at >= self._timeout_seconds:
                return FAILED
            self._sleep_shortly()
        return CONNECTED

    def reconnect(self):
        """Reconnect with the same caller-provided SSID and password."""
        return self.connect()

    def is_connected(self):
        """Return whether the configured WLAN is currently connected."""
        return self._get_wlan().isconnected()

    def _get_wlan(self):
        if self._wlan is None:
            if self._network_module is None:
                raise RuntimeError("MicroPython network module is unavailable")
            self._wlan = self._network_module.WLAN(self._network_module.STA_IF)
        return self._wlan

    def _now(self):
        if self._time_module is None:
            raise RuntimeError("time module is unavailable")
        if hasattr(self._time_module, "monotonic"):
            return self._time_module.monotonic()
        return self._time_module.time()

    def _sleep_shortly(self):
        if hasattr(self._time_module, "sleep_ms"):
            self._time_module.sleep_ms(100)
        else:
            self._time_module.sleep(0.1)
