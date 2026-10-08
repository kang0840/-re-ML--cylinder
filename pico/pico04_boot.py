"""Secret-free automatic startup for the pico04 firmware build."""

import machine
import os

PICO_ID = "pico04"
CYLINDER_ID = "cylinder_04"
EXPECTED_UID = ""
_RUNTIME = None


def _load_secrets():
    try:
        import device_secrets
    except ImportError:
        print("pico04 configuration required; network startup skipped")
        return None
    required = ("WIFI_PASSWORD", "BROKER_HOST", "MQTT_PASSWORD")
    if any(not hasattr(device_secrets, name) for name in required):
        print("pico04 configuration incomplete; network startup skipped")
        return None
    return device_secrets


def start():
    global _RUNTIME
    if not EXPECTED_UID:
        print("pico04 UID registration required; network startup skipped")
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
