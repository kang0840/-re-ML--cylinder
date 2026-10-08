"""Streaming Q15 FIR decimation for SPH0645 16 kHz PCM."""

try:
    import micropython
except ImportError:

    class _MicroPythonCompatibility:
        @staticmethod
        def native(function):
            return function

    micropython = _MicroPythonCompatibility()


INPUT_SAMPLE_RATE = 16000
OUTPUT_SAMPLE_RATE = 4000
DECIMATION_FACTOR = 4
FIR_CUTOFF_HZ = 1350

# 63-tap Hamming-windowed low-pass coefficients, scaled by 2**15.
# Designed offline: 0-1 kHz max deviation about 0.192 dB; >=2 kHz
# attenuation about 55.25 dB after Q15 quantization.
FIR_Q15_COEFFICIENTS = (
    -18,
    -6,
    11,
    29,
    45,
    52,
    43,
    13,
    -37,
    -96,
    -146,
    -162,
    -126,
    -29,
    116,
    272,
    389,
    412,
    300,
    48,
    -307,
    -678,
    -949,
    -994,
    -713,
    -63,
    925,
    2138,
    3398,
    4502,
    5255,
    5520,
    5255,
    4502,
    3398,
    2138,
    925,
    -63,
    -713,
    -994,
    -949,
    -678,
    -307,
    48,
    300,
    412,
    389,
    272,
    116,
    -29,
    -126,
    -162,
    -146,
    -96,
    -37,
    13,
    43,
    52,
    45,
    29,
    11,
    -6,
    -18,
)


class Sph0645Decimator:
    """Preserve FIR and decimation state across incoming PCM chunks."""

    def __init__(self):
        self._history = [0] * len(FIR_Q15_COEFFICIENTS)
        self._write_index = 0
        self._phase = 0

    def reset(self):
        """Clear state only at an explicit stream boundary."""
        for index in range(len(self._history)):
            self._history[index] = 0
        self._write_index = 0
        self._phase = 0

    def process(self, samples):
        """Yield 4 kHz signed PCM samples from a 16 kHz input iterable."""
        for sample in samples:
            if not isinstance(sample, int):
                raise ValueError("PCM samples must be integers")
            self._history[self._write_index] = sample
            self._write_index = (self._write_index + 1) % len(self._history)
            if self._phase == 0:
                yield self._filter_current_sample()
            self._phase = (self._phase + 1) % DECIMATION_FACTOR

    def process_pcm24(self, buffer, valid_byte_count):
        """Decode and decimate one raw I2S chunk with minimal Python overhead."""
        if not isinstance(valid_byte_count, int):
            raise ValueError("valid_byte_count must be an integer")
        if valid_byte_count < 0 or valid_byte_count > len(buffer):
            raise ValueError("valid_byte_count is outside the buffer")
        if valid_byte_count % 4 != 0:
            raise ValueError("valid_byte_count must contain complete 32-bit samples")
        return self._process_pcm24_native(buffer, valid_byte_count)

    @micropython.native
    def _process_pcm24_native(self, buffer, valid_byte_count):
        raw = memoryview(buffer)
        history = self._history
        history_length = len(history)
        coefficients = FIR_Q15_COEFFICIENTS
        write_index = self._write_index
        phase = self._phase

        input_count = valid_byte_count // 4
        first_output = 0 if phase == 0 else DECIMATION_FACTOR - phase
        if first_output >= input_count:
            output_count = 0
        else:
            output_count = 1 + (input_count - 1 - first_output) // DECIMATION_FACTOR
        outputs = [0] * output_count

        offset = 0
        output_index = 0
        while offset < valid_byte_count:
            container = (
                raw[offset]
                | (raw[offset + 1] << 8)
                | (raw[offset + 2] << 16)
                | (raw[offset + 3] << 24)
            )
            sample = container >> 8
            if sample & (1 << 23):
                sample -= 1 << 24

            history[write_index] = sample
            write_index += 1
            if write_index == history_length:
                write_index = 0

            if phase == 0:
                newest_index = write_index - 1
                if newest_index < 0:
                    newest_index += history_length
                accumulator = 0
                coefficient_index = 0
                while coefficient_index < history_length // 2:
                    left_index = newest_index - coefficient_index
                    if left_index < 0:
                        left_index += history_length
                    right_index = newest_index - (
                        history_length - 1 - coefficient_index
                    )
                    if right_index < 0:
                        right_index += history_length
                    accumulator += coefficients[coefficient_index] * (
                        history[left_index] + history[right_index]
                    )
                    coefficient_index += 1

                center_index = newest_index - history_length // 2
                if center_index < 0:
                    center_index += history_length
                accumulator += coefficients[history_length // 2] * history[center_index]
                outputs[output_index] = accumulator >> 15
                output_index += 1

            phase += 1
            if phase == DECIMATION_FACTOR:
                phase = 0
            offset += 4

        self._write_index = write_index
        self._phase = phase
        return outputs

    def _filter_current_sample(self):
        accumulator = 0
        history_length = len(self._history)
        newest_index = (self._write_index - 1) % history_length
        for coefficient_index in range(history_length // 2):
            left_index = (newest_index - coefficient_index) % history_length
            right_index = (
                newest_index - (history_length - 1 - coefficient_index)
            ) % history_length
            accumulator += FIR_Q15_COEFFICIENTS[coefficient_index] * (
                self._history[left_index] + self._history[right_index]
            )
        center_index = (newest_index - history_length // 2) % history_length
        accumulator += (
            FIR_Q15_COEFFICIENTS[history_length // 2] * self._history[center_index]
        )
        return accumulator >> 15
