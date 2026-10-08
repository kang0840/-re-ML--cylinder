"""Pico W startup composition for Wi-Fi, NTP, and MQTT readiness."""

import sys


def _add_module_path(path):
    if path not in sys.path:
        sys.path.insert(0, path)


try:
    _MODULE_FILE = __file__.replace("\\", "/")
    _BASE_DIR = _MODULE_FILE.rsplit("/", 1)[0] if "/" in _MODULE_FILE else "."
except (NameError, AttributeError):
    _BASE_DIR = "."

for _directory in (
    "Wi-Fi",
    "timestamp",
    "sequence_id",
    "Message",
    "sensor",
    "reconnect",
    "MQTT/MQTT Client",
):
    _add_module_path("%s/%s" % (_BASE_DIR, _directory))

from client import CLIENT_CYLINDER_MAP, PicoMqttPublisher, sensor_topic
from i2s_microphones import I2SMicrophones
from message import build_payload, build_sensor_chunk
from pcm_decoder import decode_inmp441_chunk
from reconnect import ReconnectionCoordinator
from sequence_id import SessionSequenceState
from timestamp import TimestampProvider
from wifi import CONNECTED, WiFiConnection
from sph0645_decimator import Sph0645Decimator

WIFI_SSID = "DESKTOP-S9R9HQ2 5984"
POWER_LED_DURATION_MS = 3000
READY_LED_DURATION_MS = 5000


class StartupStatusLed:
    """Show power-on and first successful sensor delivery on the Pico W LED."""

    def __init__(self, machine_module=None, time_module=None):
        if machine_module is None:
            try:
                import machine as machine_module
            except ImportError:
                machine_module = None
        if time_module is None:
            try:
                import time as time_module
            except ImportError:
                time_module = None
        self._machine = machine_module
        self._time = time_module
        self._led = None
        self._ready_deadline = None
        self._ready_signaled = False
        if machine_module is not None:
            try:
                self._led = machine_module.Pin("LED", machine_module.Pin.OUT)
            except (AttributeError, TypeError, ValueError):
                self._led = None

    def signal_power_on(self):
        """Light for three seconds as immediate proof that power is present."""
        if self._led is None:
            return
        self._led.value(1)
        self._sleep_ms(POWER_LED_DURATION_MS)
        self._led.value(0)

    def signal_operational(self):
        """Light once for five seconds after the first acknowledged sensor publish."""
        if self._led is None or self._ready_signaled:
            return
        self._ready_signaled = True
        self._led.value(1)
        if self._time is not None and hasattr(self._time, "ticks_add"):
            self._ready_deadline = self._time.ticks_add(
                self._time.ticks_ms(), READY_LED_DURATION_MS
            )

    def update(self):
        """Turn off the ready light from the normal sensor loop, never an IRQ."""
        if self._ready_deadline is None or self._time is None:
            return
        if self._time.ticks_diff(self._time.ticks_ms(), self._ready_deadline) >= 0:
            self._led.value(0)
            self._ready_deadline = None

    def shutdown(self):
        """Leave the indicator off."""
        self._ready_deadline = None
        if self._led is not None:
            self._led.value(0)

    def _sleep_ms(self, duration_ms):
        if self._time is None:
            return
        if hasattr(self._time, "sleep_ms"):
            self._time.sleep_ms(duration_ms)
        else:
            self._time.sleep(duration_ms / 1000.0)


class PicoRuntime:
    """Prepared runtime dependencies for the future sensor publish stage."""

    def __init__(
        self,
        client_id,
        cylinder_id,
        timestamp_provider,
        publisher,
        microphones=None,
        sph0645_decimator=None,
        reconnection_coordinator=None,
        time_module=None,
        reconnect_delay_seconds=2,
        startup_status_led=None,
    ):
        self.client_id = client_id
        self.cylinder_id = cylinder_id
        self.timestamp_provider = timestamp_provider
        self.publisher = publisher
        self.microphones = microphones
        self.sph0645_decimator = sph0645_decimator
        self.reconnection_coordinator = reconnection_coordinator
        self.time_module = time_module
        self.reconnect_delay_seconds = reconnect_delay_seconds
        self.startup_status_led = startup_status_led

    def publish_sensor_chunk(self):
        """Read one paired raw chunk and publish one new QoS 1 logical message."""
        if self.microphones is None or self.sph0645_decimator is None:
            raise RuntimeError("sensor pipeline is not enabled")
        if self.startup_status_led is not None:
            self.startup_status_led.update()
        sph_buffer, sph_byte_count = self.microphones.read_sph0645()
        inmp_buffer, inmp_byte_count = self.microphones.read_inmp441()
        sph0645 = build_sensor_chunk(
            4000,
            self.sph0645_decimator.process_pcm24(sph_buffer, sph_byte_count),
        )
        inmp441 = build_sensor_chunk(
            16000,
            decode_inmp441_chunk(inmp_buffer, inmp_byte_count),
        )
        sequence_id = self.publisher.publish_new(
            self.cylinder_id,
            self.timestamp_provider.get_timestamp(),
            sph0645,
            inmp441,
        )
        if self.startup_status_led is not None:
            self.startup_status_led.signal_operational()
            self.startup_status_led.update()
        return sequence_id

    def run_forever(self):
        """Continuously publish chunks and restore transport without resetting IDs."""
        if self.microphones is None or self.sph0645_decimator is None:
            raise RuntimeError("sensor pipeline is not enabled")
        if self.reconnection_coordinator is None:
            raise RuntimeError("reconnection coordinator is unavailable")
        try:
            while True:
                try:
                    self.publish_sensor_chunk()
                except OSError:
                    self._restore_connection()
        finally:
            self.deinit()

    def _restore_connection(self):
        while True:
            try:
                self.reconnection_coordinator.restore_connection()
                return
            except OSError:
                if self.time_module is None:
                    raise
                self.time_module.sleep(self.reconnect_delay_seconds)

    def deinit(self):
        """Release I2S resources when this runtime owns an enabled pipeline."""
        try:
            if self.microphones is not None:
                self.microphones.deinit()
        finally:
            try:
                self.publisher.disconnect()
            finally:
                if self.startup_status_led is not None:
                    self.startup_status_led.shutdown()


def validate_device_identity(client_id, cylinder_id, expected_uid, unique_id_provider):
    """Reject a copied device configuration before any network connection."""
    if client_id not in CLIENT_CYLINDER_MAP:
        raise ValueError("client_id must be one of pico01 through pico06")
    if cylinder_id != CLIENT_CYLINDER_MAP[client_id]:
        raise ValueError("cylinder_id must match the fixed Pico mapping")
    if not isinstance(expected_uid, str) or not expected_uid:
        raise ValueError("expected_uid is required for device identity validation")
    actual_uid = bytes(unique_id_provider()).hex()
    if actual_uid.lower() != expected_uid.lower():
        raise RuntimeError("DEVICE UID MISMATCH")
    return actual_uid


def run(
    client_id,
    wifi_password,
    broker_host,
    mqtt_password,
    random_bytes,
    wifi_connection_factory=WiFiConnection,
    timestamp_provider_factory=TimestampProvider,
    publisher_factory=PicoMqttPublisher,
    identity_state_factory=SessionSequenceState,
    payload_builder=build_payload,
    enable_sensor_pipeline=False,
    microphones_factory=I2SMicrophones,
    sph0645_decimator_factory=Sph0645Decimator,
    time_module=None,
    expected_uid=None,
    unique_id_provider=None,
    configured_cylinder_id=None,
    startup_status_led_factory=StartupStatusLed,
):
    """Prepare a connected publisher without generating or sending sensor data."""
    if client_id not in CLIENT_CYLINDER_MAP:
        raise ValueError("client_id must be one of pico01 through pico06")

    cylinder_id = CLIENT_CYLINDER_MAP[client_id]
    if configured_cylinder_id is not None and configured_cylinder_id != cylinder_id:
        raise ValueError("configured_cylinder_id must match the fixed Pico mapping")
    if expected_uid is not None or unique_id_provider is not None:
        if expected_uid is None or unique_id_provider is None:
            raise ValueError(
                "expected_uid and unique_id_provider must be supplied together"
            )
        validate_device_identity(
            client_id,
            configured_cylinder_id or cylinder_id,
            expected_uid,
            unique_id_provider,
        )
    startup_status_led = startup_status_led_factory()
    startup_status_led.signal_power_on()
    identity_state = identity_state_factory(random_bytes)
    wifi_connection = wifi_connection_factory(WIFI_SSID, wifi_password)
    if wifi_connection.connect() != CONNECTED:
        raise RuntimeError("Wi-Fi connection failed")

    timestamp_provider = timestamp_provider_factory()
    if not timestamp_provider.synchronize():
        raise RuntimeError("NTP synchronization failed")

    publisher = publisher_factory(
        sensor_topic(cylinder_id),
        identity_state,
        payload_builder,
        broker_host,
        client_id=client_id,
        username=client_id,
        password=mqtt_password,
        timestamp_provider=timestamp_provider,
    )
    publisher.connect()
    if time_module is None:
        import time as time_module

    def reconnect_wifi():
        if wifi_connection.reconnect() != CONNECTED:
            raise OSError("Wi-Fi reconnection failed")

    def reconnect_mqtt():
        publisher.reconnect()
        publisher.republish_pending()

    reconnection_coordinator = ReconnectionCoordinator(
        identity_state,
        reconnect_wifi,
        reconnect_mqtt,
    )
    microphones = None
    decimator = None
    if enable_sensor_pipeline:
        microphones = microphones_factory().initialize()
        decimator = sph0645_decimator_factory()
    return PicoRuntime(
        client_id,
        cylinder_id,
        timestamp_provider,
        publisher,
        microphones,
        decimator,
        reconnection_coordinator,
        time_module,
        startup_status_led=startup_status_led,
    )


def _start_device_boot():
    """Start the single device-specific boot module stored on this Pico."""
    import os

    boot_modules = []
    root_files = os.listdir("/")
    for number in range(1, 7):
        module_name = "pico%02d_boot" % number
        if "%s.py" % module_name in root_files:
            boot_modules.append(module_name)
    if len(boot_modules) != 1:
        raise RuntimeError("exactly one picoXX_boot.py file is required")
    module_name = boot_modules[0]
    print(module_name.upper(), "STARTING")
    __import__(module_name).start()


if __name__ == "__main__" and sys.implementation.name == "micropython":
    _start_device_boot()
