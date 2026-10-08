"""NTP-backed Pico timestamps for the project Asia/Seoul payload contract."""

try:
    import ntptime as _ntptime
except ImportError:
    _ntptime = None

try:
    import time as _time
except ImportError:
    _time = None


SEOUL_UTC_OFFSET_SECONDS = 9 * 60 * 60


class TimestampProvider:
    """Synchronize Pico RTC with NTP before generating sensor timestamps."""

    def __init__(self, ntp_module=None, time_module=None):
        self._ntp_module = ntp_module or _ntptime
        self._time_module = time_module or _time
        self.time_synced = False

    def synchronize(self):
        """Set Pico RTC from NTP and report whether synchronization succeeded."""
        if self._ntp_module is None or self._time_module is None:
            self.time_synced = False
            return False
        try:
            self._ntp_module.settime()
        except Exception:
            self.time_synced = False
            return False
        self.time_synced = True
        return True

    def get_timestamp(self):
        """Return ISO 8601 +09:00 only after a successful NTP synchronization."""
        if not self.time_synced:
            raise RuntimeError("timestamp is unavailable before NTP synchronization")
        utc_epoch = self._time_module.time()
        local_time = self._time_module.gmtime(utc_epoch + SEOUL_UTC_OFFSET_SECONDS)
        return "%04d-%02d-%02dT%02d:%02d:%02d+09:00" % (
            local_time[0],
            local_time[1],
            local_time[2],
            local_time[3],
            local_time[4],
            local_time[5],
        )
