"""Decode RP2 MicroPython 32-bit I2S RX chunks into signed 24-bit PCM."""

try:
    import micropython
except ImportError:

    class _MicroPythonCompatibility:
        @staticmethod
        def native(function):
            return function

    micropython = _MicroPythonCompatibility()


RAW_BYTES_PER_SAMPLE = 4
MICROPHONE_DATA_BITS = 24
CONTAINER_PADDING_BITS = 8
SIGN_BIT = 1 << (MICROPHONE_DATA_BITS - 1)
SIGN_RANGE = 1 << MICROPHONE_DATA_BITS


def decode_sph0645(buffer, valid_byte_count):
    """Yield signed 24-bit SPH0645 PCM values from one valid raw chunk.

    The SPH0645 has 18-bit precision; its lower six bits remain zero in the
    returned 24-bit samples and are intentionally not rescaled here.
    """
    return _decode_pcm24(buffer, valid_byte_count)


def decode_inmp441(buffer, valid_byte_count):
    """Yield signed 24-bit INMP441 PCM values from one valid raw chunk."""
    return _decode_pcm24(buffer, valid_byte_count)


def decode_inmp441_chunk(buffer, valid_byte_count):
    """Decode one INMP441 chunk eagerly using the native emitter on MicroPython."""
    _validate_chunk(buffer, valid_byte_count)
    return _decode_pcm24_chunk(buffer, valid_byte_count)


@micropython.native
def _decode_pcm24_chunk(buffer, valid_byte_count):
    """Decode an indexable chunk without generator or per-sample function overhead."""
    raw = memoryview(buffer)
    sample_count = valid_byte_count // RAW_BYTES_PER_SAMPLE
    samples = [0] * sample_count
    offset = 0
    output_index = 0
    while offset < valid_byte_count:
        container = (
            raw[offset]
            | (raw[offset + 1] << 8)
            | (raw[offset + 2] << 16)
            | (raw[offset + 3] << 24)
        )
        sample = container >> CONTAINER_PADDING_BITS
        if sample & SIGN_BIT:
            sample -= SIGN_RANGE
        samples[output_index] = sample
        output_index += 1
        offset += RAW_BYTES_PER_SAMPLE
    return samples


def _decode_pcm24(buffer, valid_byte_count):
    """Yield PCM samples without allocating a decoded chunk-sized list."""
    _validate_chunk(buffer, valid_byte_count)
    raw = memoryview(buffer)
    for offset in range(0, valid_byte_count, RAW_BYTES_PER_SAMPLE):
        container = (
            raw[offset]
            | (raw[offset + 1] << 8)
            | (raw[offset + 2] << 16)
            | (raw[offset + 3] << 24)
        )
        sample = container >> CONTAINER_PADDING_BITS
        if sample & SIGN_BIT:
            sample -= SIGN_RANGE
        yield sample


def _validate_chunk(buffer, valid_byte_count):
    if not isinstance(valid_byte_count, int):
        raise ValueError("valid_byte_count must be an integer")
    if valid_byte_count < 0 or valid_byte_count > len(buffer):
        raise ValueError("valid_byte_count is outside the buffer")
    if valid_byte_count % RAW_BYTES_PER_SAMPLE != 0:
        raise ValueError("valid_byte_count must contain complete 32-bit samples")
