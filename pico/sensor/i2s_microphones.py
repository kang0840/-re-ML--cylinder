"""Chunked raw PCM capture from the two Pico W I2S microphones."""

try:
    import machine as _machine
except ImportError:
    _machine = None

try:
    import time as _time
except ImportError:
    _time = None


SPH0645_I2S_ID = 0
SPH0645_SCK_PIN = 6
SPH0645_WS_PIN = 7
SPH0645_SD_PIN = 8
SPH0645_CHANNEL_PIN = 9
SPH0645_POWER_PIN = 22

INMP441_I2S_ID = 1
INMP441_SCK_PIN = 2
INMP441_WS_PIN = 3
INMP441_SD_PIN = 4
INMP441_CHANNEL_PIN = 27
INMP441_POWER_PIN = 28

I2S_ACQUISITION_RATE = 16000
SPH0645_ANALYSIS_SAMPLE_RATE = 4000
INMP441_ANALYSIS_SAMPLE_RATE = 16000
I2S_BITS = 32
I2S_INTERNAL_BUFFER_BYTES = 8192
READ_BUFFER_BYTES = 4096
POWER_STABILIZATION_MS = 10


class I2SMicrophones:
    """Own two I2S RX buses and reuse one raw read buffer per microphone."""

    def __init__(self, i2s_class=None, pin_class=None, time_module=None):
        self._i2s_class = i2s_class or getattr(_machine, "I2S", None)
        self._pin_class = pin_class or getattr(_machine, "Pin", None)
        self._time_module = time_module or _time
        self._sph0645_i2s = None
        self._inmp441_i2s = None
        self._sph0645_power = None
        self._inmp441_power = None
        self._sph0645_channel = None
        self._inmp441_channel = None
        self._sph0645_buffer = bytearray(READ_BUFFER_BYTES)
        self._inmp441_buffer = bytearray(READ_BUFFER_BYTES)
        self._initialized = False

    def initialize(self):
        """Create both configured I2S RX buses once and return this instance."""
        if self._initialized:
            return self
        if self._i2s_class is None or self._pin_class is None:
            raise RuntimeError("machine.I2S and machine.Pin are unavailable")

        try:
            self._configure_control_pins()
            self._sph0645_i2s = self._create_i2s(
                SPH0645_I2S_ID,
                SPH0645_SCK_PIN,
                SPH0645_WS_PIN,
                SPH0645_SD_PIN,
            )
            self._inmp441_i2s = self._create_i2s(
                INMP441_I2S_ID,
                INMP441_SCK_PIN,
                INMP441_WS_PIN,
                INMP441_SD_PIN,
            )
        except Exception:
            self.deinit()
            raise

        self._initialized = True
        return self

    def read_sph0645(self):
        """Return the reusable SPH0645 buffer and its valid byte count."""
        self._require_initialized()
        return self._read_into(self._sph0645_i2s, self._sph0645_buffer)

    def read_inmp441(self):
        """Return the reusable INMP441 buffer and its valid byte count."""
        self._require_initialized()
        return self._read_into(self._inmp441_i2s, self._inmp441_buffer)

    def deinit(self):
        """Attempt to deinitialize both buses and leave this object uninitialized."""
        errors = []
        for attribute in ("_sph0645_i2s", "_inmp441_i2s"):
            i2s = getattr(self, attribute)
            if i2s is None:
                continue
            try:
                i2s.deinit()
            except Exception as error:
                errors.append(error)
            finally:
                setattr(self, attribute, None)
        for attribute in ("_sph0645_power", "_inmp441_power"):
            power_pin = getattr(self, attribute)
            if power_pin is None:
                continue
            try:
                power_pin.value(0)
            except Exception as error:
                errors.append(error)
            finally:
                setattr(self, attribute, None)
        self._sph0645_channel = None
        self._inmp441_channel = None
        self._initialized = False
        if errors:
            raise errors[0]

    def _configure_control_pins(self):
        self._sph0645_power = self._pin_class(SPH0645_POWER_PIN, self._pin_class.OUT)
        self._inmp441_power = self._pin_class(INMP441_POWER_PIN, self._pin_class.OUT)
        self._sph0645_channel = self._pin_class(
            SPH0645_CHANNEL_PIN, self._pin_class.OUT
        )
        self._inmp441_channel = self._pin_class(
            INMP441_CHANNEL_PIN, self._pin_class.OUT
        )

        self._sph0645_power.value(0)
        self._inmp441_power.value(0)
        self._sph0645_channel.value(0)
        self._inmp441_channel.value(0)
        self._sph0645_power.value(1)
        self._inmp441_power.value(1)

        if self._time_module is not None:
            if hasattr(self._time_module, "sleep_ms"):
                self._time_module.sleep_ms(POWER_STABILIZATION_MS)
            else:
                self._time_module.sleep(POWER_STABILIZATION_MS / 1000)

    def _create_i2s(self, i2s_id, sck_pin, ws_pin, sd_pin):
        return self._i2s_class(
            i2s_id,
            sck=self._pin_class(sck_pin),
            ws=self._pin_class(ws_pin),
            sd=self._pin_class(sd_pin),
            mode=self._i2s_class.RX,
            bits=I2S_BITS,
            format=self._i2s_class.MONO,
            rate=I2S_ACQUISITION_RATE,
            ibuf=I2S_INTERNAL_BUFFER_BYTES,
        )

    def _require_initialized(self):
        if not self._initialized:
            raise RuntimeError("I2S microphones are not initialized")

    @staticmethod
    def _read_into(i2s, buffer):
        byte_count = i2s.readinto(buffer)
        if not isinstance(byte_count, int) or not 0 <= byte_count <= len(buffer):
            raise RuntimeError("I2S readinto returned an invalid byte count")
        return buffer, byte_count
