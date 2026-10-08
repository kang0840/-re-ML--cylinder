"""Pico MQTT chunk payload construction and validation."""

try:
    import micropython
except ImportError:

    class _MicroPythonCompatibility:
        @staticmethod
        def native(function):
            return function

    micropython = _MicroPythonCompatibility()


try:
    import binascii as _binascii
except ImportError:
    _binascii = None

REQUIRED_FIELDS = (
    "cylinder_id",
    "session_id",
    "sequence_id",
    "timestamp",
    "sph0645",
    "inmp441",
)


def build_payload(
    cylinder_id,
    session_id,
    sequence_id,
    timestamp,
    sph0645,
    inmp441,
):
    """Build one compact sensor-chunk message."""
    payload = {
        "cylinder_id": cylinder_id,
        "session_id": session_id,
        "sequence_id": sequence_id,
        "timestamp": timestamp,
        "sph0645": sph0645,
        "inmp441": inmp441,
    }
    validate_payload(payload)
    return payload


def build_sensor_chunk(sample_rate, samples):
    """Pack signed PCM as compact s32le base64 without JSON integer arrays."""
    if not isinstance(sample_rate, int) or sample_rate < 1:
        raise ValueError("sample_rate must be a positive integer")
    try:
        sample_count = len(samples)
    except TypeError:
        sample_count = None
    if sample_count is not None:
        packed = bytearray(sample_count * 4)
        _pack_indexable_samples(samples, packed)
    else:
        packed = bytearray()
        sample_count = 0
        for sample in samples:
            _validate_pcm_sample(sample)
            packed.extend(
                (
                    sample & 0xFF,
                    (sample >> 8) & 0xFF,
                    (sample >> 16) & 0xFF,
                    (sample >> 24) & 0xFF,
                )
            )
            sample_count += 1
    if sample_count < 1:
        raise ValueError("sensor chunk must contain at least one sample")
    if _binascii is None:
        raise RuntimeError("binascii is unavailable")
    encoded = _binascii.b2a_base64(bytes(packed)).strip()
    return {
        "sample_rate": sample_rate,
        "sample_format": "s32le",
        "sample_count": sample_count,
        "encoding": "base64",
        "data": encoded.decode("ascii"),
    }


def _validate_pcm_sample(sample):
    if not isinstance(sample, int) or sample < -(1 << 31) or sample >= (1 << 31):
        raise ValueError("PCM sample must fit signed 32-bit little-endian")


@micropython.native
def _pack_indexable_samples(samples, packed):
    sample_count = len(samples)
    sample_index = 0
    output_offset = 0
    while sample_index < sample_count:
        sample = samples[sample_index]
        if not isinstance(sample, int) or sample < -(1 << 31) or sample >= (1 << 31):
            raise ValueError("PCM sample must fit signed 32-bit little-endian")
        packed[output_offset] = sample & 0xFF
        packed[output_offset + 1] = (sample >> 8) & 0xFF
        packed[output_offset + 2] = (sample >> 16) & 0xFF
        packed[output_offset + 3] = (sample >> 24) & 0xFF
        sample_index += 1
        output_offset += 4


def validate_payload(payload):
    """Reject a message missing the cross-device identity contract."""
    if not isinstance(payload, dict):
        raise ValueError("payload must be a dictionary")
    for field in REQUIRED_FIELDS:
        if field not in payload or payload[field] is None or payload[field] == "":
            raise ValueError("missing required field: %s" % field)
    if isinstance(payload["sequence_id"], bool) or not isinstance(
        payload["sequence_id"], int
    ):
        raise ValueError("sequence_id must be an integer")
    if payload["sequence_id"] < 1:
        raise ValueError("sequence_id must be positive")
    if not isinstance(payload["timestamp"], str) or not payload["timestamp"].endswith(
        "+09:00"
    ):
        raise ValueError("timestamp must be an ISO 8601 string with +09:00 timezone")
    _validate_sensor_chunk("sph0645", payload["sph0645"], 4000)
    _validate_sensor_chunk("inmp441", payload["inmp441"], 16000)


def _validate_sensor_chunk(name, chunk, expected_sample_rate):
    if not isinstance(chunk, dict):
        raise ValueError("%s must be a sensor chunk object" % name)
    for field in ("sample_rate", "sample_format", "sample_count", "encoding", "data"):
        if field not in chunk:
            raise ValueError("%s is missing %s" % (name, field))
    if chunk["sample_rate"] != expected_sample_rate:
        raise ValueError("%s sample_rate is invalid" % name)
    if chunk["sample_format"] != "s32le":
        raise ValueError("%s sample_format must be s32le" % name)
    if (
        isinstance(chunk["sample_count"], bool)
        or not isinstance(chunk["sample_count"], int)
        or chunk["sample_count"] < 1
    ):
        raise ValueError("%s sample_count must be positive" % name)
    if chunk["encoding"] != "base64" or not isinstance(chunk["data"], str):
        raise ValueError("%s encoding must be base64" % name)
