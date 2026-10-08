"""Secret-free automatic startup for the pico01 firmware build."""

import machine
import os

PICO_ID = "pico01"
CYLINDER_ID = "cylinder_01"
EXPECTED_UID = "e66440a2cb41a728"
_RUNTIME = None


def _load_secrets():
    try:
        import device_secrets
    except ImportError:
        print("pico01 configuration required; network startup skipped")
        return None

    required = ("WIFI_PASSWORD", "BROKER_HOST", "MQTT_PASSWORD")
    if any(not hasattr(device_secrets, name) for name in required):
        print("pico01 configuration incomplete; network startup skipped")
        return None
    return device_secrets


def start():
    """Validate pico01 identity and start networking when secrets exist."""
    global _RUNTIME
    if not EXPECTED_UID:
        print("pico01 UID registration required; network startup skipped")
        return None
    secrets = _load_secrets()
    if secrets is None:
        return None

    from main import run

    enable_sensor_pipeline = bool(getattr(secrets, "ENABLE_SENSOR_PIPELINE", False))
    _RUNTIME = run(
        client_id=PICO_ID,
        wifi_password=secrets.WIFI_PASSWORD,
        broker_host=secrets.BROKER_HOST,
        mqtt_password=secrets.MQTT_PASSWORD,
        random_bytes=os.urandom,
        expected_uid=EXPECTED_UID,
        unique_id_provider=machine.unique_id,
        configured_cylinder_id=CYLINDER_ID,
        enable_sensor_pipeline=enable_sensor_pipeline,
    )
    if enable_sensor_pipeline:
        _RUNTIME.run_forever()
    return _RUNTIME
