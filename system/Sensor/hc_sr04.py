"""Injectable HC-SR04 distance readers for Raspberry Pi GPIO."""

import time


class HcSr04Sensor:
    """Measure one HC-SR04 without assigning a physical sensor role."""

    def __init__(
        self,
        trigger_pin,
        echo_pin,
        echo_timeout_seconds,
        gpio=None,
        clock=None,
        sleep_microseconds=None,
    ):
        if echo_timeout_seconds <= 0:
            raise ValueError("echo_timeout_seconds must be positive")
        self.trigger_pin = trigger_pin
        self.echo_pin = echo_pin
        self._echo_timeout_seconds = echo_timeout_seconds
        self._gpio = gpio or _load_gpio()
        self._clock = clock or time.monotonic
        self._sleep_microseconds = sleep_microseconds or _sleep_microseconds
        self._initialized = False

    def initialize(self):
        """Configure the declared BCM pins for one trigger/echo pair."""
        self._gpio.setup(self.trigger_pin, self._gpio.OUT)
        self._gpio.setup(self.echo_pin, self._gpio.IN)
        self._gpio.output(self.trigger_pin, self._gpio.LOW)
        self._initialized = True
        return self

    def measure_distance_cm(self):
        """Return one distance measurement or raise TimeoutError."""
        if not self._initialized:
            raise RuntimeError("HC-SR04 sensor is not initialized")
        self._gpio.output(self.trigger_pin, self._gpio.HIGH)
        self._sleep_microseconds(10)
        self._gpio.output(self.trigger_pin, self._gpio.LOW)

        self._wait_for_level(self._gpio.LOW)
        pulse_started_at = self._clock()
        self._wait_for_level(self._gpio.HIGH)
        pulse_finished_at = self._clock()
        return (pulse_finished_at - pulse_started_at) * 17150.0

    def _wait_for_level(self, level):
        deadline = self._clock() + self._echo_timeout_seconds
        while self._gpio.input(self.echo_pin) == level:
            if self._clock() >= deadline:
                raise TimeoutError("HC-SR04 echo timed out")


class HcSr04Array:
    """Read the three neutral HC-SR04 sensors as one named measurement set."""

    def __init__(self, hc_sr04_1, hc_sr04_2, hc_sr04_3):
        self._sensors = {
            "HC_SR04_1": hc_sr04_1,
            "HC_SR04_2": hc_sr04_2,
            "HC_SR04_3": hc_sr04_3,
        }

    def initialize(self):
        for sensor in self._sensors.values():
            sensor.initialize()
        return self

    def measure_all_cm(self):
        return {
            sensor_name: sensor.measure_distance_cm()
            for sensor_name, sensor in self._sensors.items()
        }


def _load_gpio():
    try:
        import RPi.GPIO as gpio
    except ImportError as error:
        raise RuntimeError(
            "RPi.GPIO is unavailable; inject a GPIO implementation"
        ) from error
    gpio.setmode(gpio.BCM)
    return gpio


def _sleep_microseconds(microseconds):
    time.sleep(microseconds / 1000000.0)
