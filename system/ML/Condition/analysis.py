"""Cycle-level feature extraction, normal baseline, and condition interfaces."""

from math import sqrt
from dataclasses import dataclass
from collections.abc import Mapping
from numbers import Integral, Real

PREPROCESSING_VERSION = "mean_remove_analysis_unit_v1"


def preprocess_samples(samples):
    """Center one analysis unit on a new float64 array; never mutate Raw PCM.

    Training and realtime must use the same unit boundaries. This is DC
    removal, not a band-pass filter, clipping repair or calibration.
    """
    import numpy as np

    raw = np.asarray(samples)
    if raw.ndim != 1 or not raw.size or raw.dtype.kind not in "iuf":
        raise ValueError("samples must be a non-empty real numeric sequence")
    values = raw.astype(np.float64, copy=True)
    if not np.all(np.isfinite(values)):
        raise ValueError("samples must be finite")
    values -= np.mean(values)
    return values


def make_packet_metrics(payload):
    """Display-only per-packet AC magnitude, not Cycle or training features."""
    import numpy as np

    sensors = {}
    for name in ("sph0645", "inmp441"):
        chunk = payload[name]
        values = preprocess_samples(chunk["samples"])
        sensors[name] = {
            "rms": float(np.sqrt(np.mean(values * values))),
            "peak": float(np.max(np.abs(values))),
            "sample_count": len(values),
            "sample_rate": chunk["sample_rate"],
        }
    return {"preprocessing_version": PREPROCESSING_VERSION, **sensors}


@dataclass(frozen=True)
class STFTResult:
    """Frequency rows, frame columns; times are window-center seconds."""

    frequencies: object
    times: object
    magnitude: object


@dataclass(frozen=True)
class WebPreviewConfig:
    """External Web-only sizing/rate/retention, never an ML configuration."""

    frequency_bins: int
    time_bins: int
    max_bytes: int
    generate_interval_seconds: float
    store_interval_seconds: float
    keep_rows: int

    def __post_init__(self):
        from math import isfinite

        for name in ("frequency_bins", "time_bins", "max_bytes", "keep_rows"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError("CONFIG_REQUIRED: " + name)
        for name in ("generate_interval_seconds", "store_interval_seconds"):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, Real)
                or not isfinite(value)
                or value <= 0
            ):
                raise ValueError("CONFIG_REQUIRED: " + name)


def reduce_stft_preview(snapshot, config):
    """Mean-pool display bins; preserve originals and relative window times.

    Two sensors require at most 2*F*T magnitudes and 2*(F+T) axis values.
    Serialization is measured, not assumed. Exceeding the external byte cap
    rejects the preview rather than silently altering a production policy.
    """
    import json
    import numpy as np

    if not isinstance(config, WebPreviewConfig):
        raise ValueError("CONFIG_REQUIRED: WebPreviewConfig")
    output = {}
    for sensor in ("sph0645", "inmp441"):
        result = snapshot["sensors"][sensor]["result"]
        matrix = np.asarray(result.magnitude)
        if (
            matrix.shape != (len(result.frequencies), len(result.times))
            or not matrix.size
            or not np.all(np.isfinite(matrix))
            or np.any(matrix < 0)
        ):
            raise ValueError("invalid STFT preview input")
        f_groups = np.array_split(
            np.arange(matrix.shape[0]), min(config.frequency_bins, matrix.shape[0])
        )
        t_groups = np.array_split(
            np.arange(matrix.shape[1]), min(config.time_bins, matrix.shape[1])
        )
        output[sensor] = {
            "frequencies": [float(np.mean(result.frequencies[g])) for g in f_groups],
            "relative_times": [float(np.mean(result.times[g])) for g in t_groups],
            "magnitude": [
                [float(np.mean(matrix[np.ix_(fg, tg)])) for tg in t_groups]
                for fg in f_groups
            ],
        }
    size = len(
        json.dumps(output, separators=(",", ":"), allow_nan=False).encode("utf-8")
    )
    if size > config.max_bytes:
        raise ValueError("PREVIEW_TOO_LARGE")
    return output


def calculate_stft(samples, sample_rate, config):
    """Calculate a one-sided magnitude STFT from in-memory real samples.

    Config supplies window_size, hop_length, n_fft and window_function (SciPy
    get_window name/tuple or explicit real window array). Only complete windows
    are returned; an incomplete tail is omitted, with no edge-filled frames.
    Times use sample zero as the origin and the window center as each frame's
    position. Magnitude uses SciPy's unit-sum window normalization: an interior
    unit-amplitude bin-centered sine has magnitude 0.5, not a doubled amplitude,
    PSD, dB, or calibrated sound pressure. No detrending or frequency-band filter
    is applied. This is calculation only, not motion detection or classification.
    """
    import numpy as np
    from scipy.signal import ShortTimeFFT, get_window

    if (
        isinstance(sample_rate, (bool, np.bool_))
        or not isinstance(sample_rate, Real)
        or not np.isfinite(sample_rate)
        or sample_rate <= 0
    ):
        raise ValueError("sample_rate must be a finite positive real number")
    if config is None:
        raise ValueError("CONFIG_REQUIRED: STFT configuration is missing")

    def required(name):
        value = (
            config.get(name)
            if isinstance(config, Mapping)
            else getattr(config, name, None)
        )
        if value is None:
            raise ValueError("CONFIG_REQUIRED: " + name)
        return value

    sizes = [required(name) for name in ("window_size", "hop_length", "n_fft")]
    if any(
        isinstance(v, (bool, np.bool_)) or not isinstance(v, Integral) or v <= 0
        for v in sizes
    ):
        raise ValueError("STFT sizes must be positive integers")
    window_size, hop_length, n_fft = map(int, sizes)
    if hop_length > window_size or n_fft < window_size:
        raise ValueError("hop_length must not exceed window_size; n_fft must cover it")
    spec = required("window_function")
    try:
        raw = np.asarray(samples)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "samples must be a one-dimensional real numeric array"
        ) from exc
    if raw.ndim != 1 or raw.size < window_size or raw.dtype.kind not in "iuf":
        raise ValueError(
            "samples must be real numeric, one-dimensional and cover a window"
        )
    values = raw.astype(np.float64)
    if not np.all(np.isfinite(values)):
        raise ValueError("samples must be finite")
    try:
        if isinstance(spec, (str, tuple)):
            window = get_window(spec, window_size, fftbins=True)
        else:
            window = np.asarray(spec)
            if window.dtype.kind not in "iuf":
                raise ValueError("window must be real numeric")
            window = window.astype(np.float64)
        if (
            window.ndim != 1
            or len(window) != window_size
            or not np.all(np.isfinite(window))
            or not np.isfinite(window.sum())
            or window.sum() == 0
        ):
            raise ValueError(
                "window must be finite, matching size and have nonzero sum"
            )
        transform = ShortTimeFFT(
            window,
            hop_length,
            float(sample_rate),
            mfft=n_fft,
            fft_mode="onesided",
            scale_to="magnitude",
        )
        frames = 1 + (len(values) - window_size) // hop_length
        center = window_size // 2
        magnitude = np.abs(transform.stft(values, p0=0, p1=frames, k_offset=center))
        frequencies = transform.f.copy()
        times = transform.t(len(values), p0=0, p1=frames, k_offset=center).copy()
    except (TypeError, ValueError, OverflowError, ZeroDivisionError) as exc:
        raise ValueError("Invalid STFT configuration or sampling rate") from exc
    if not all(np.all(np.isfinite(v)) for v in (frequencies, times, magnitude)):
        raise ValueError("STFT result is nonfinite")
    return STFTResult(frequencies, times, magnitude)


MODEL_FEATURE_NAMES = (
    "mean",
    "standard_deviation",
    "rms",
    "maximum",
    "minimum",
    "peak",
    "peak_to_peak",
    "crest_factor",
    "dominant_frequency",
    "dominant_amplitude",
    "spectral_energy",
)


class CycleFeatureExtractor:
    """Extract compact time and spectrum features on Raspberry Pi."""

    def __init__(self, numpy_module=None):
        if numpy_module is None:
            try:
                import numpy as numpy_module
            except ImportError as error:
                raise RuntimeError(
                    "numpy is required for FFT feature extraction"
                ) from error
        self._np = numpy_module

    def extract(self, sph0645_samples, inmp441_samples):
        sph = self._extract_sensor(sph0645_samples, 4000, (2.0, 1000.0))
        inmp = self._extract_sensor(inmp441_samples, 16000, None)
        return {
            "sph0645_rms": sph["rms"],
            "inmp441_rms": inmp["rms"],
            "sph0645_peak": sph["peak"],
            "inmp441_peak": inmp["peak"],
            "sph0645_peak_to_peak": sph["peak_to_peak"],
            "inmp441_peak_to_peak": inmp["peak_to_peak"],
            "sph0645_crest_factor": sph["crest_factor"],
            "inmp441_crest_factor": inmp["crest_factor"],
            "fft_features": {"sph0645": sph, "inmp441": inmp},
        }

    def extract_chunks(self, chunks):
        """Extract one Cycle result from decoded parser payloads."""
        sph0645_samples = []
        inmp441_samples = []
        for chunk in chunks:
            sph0645_samples.extend(chunk["sph0645"]["samples"])
            inmp441_samples.extend(chunk["inmp441"]["samples"])
        return self.extract(sph0645_samples, inmp441_samples)

    def extract_model_features(self, sph0645_samples, inmp441_samples):
        """Return the saved condition models' ordered 11-feature inputs."""
        return {
            "vibration": self._extract_model_sensor(sph0645_samples, 4000),
            "sound": self._extract_model_sensor(inmp441_samples, 16000),
        }

    def _extract_sensor(self, samples, sample_rate, frequency_range):
        np = self._np
        values = preprocess_samples(samples)
        if values.ndim != 1 or values.size == 0:
            raise ValueError(
                "sensor samples must be a non-empty one-dimensional sequence"
            )
        rms = float(sqrt(float(np.mean(values * values))))
        peak = float(np.max(np.abs(values)))
        peak_to_peak = float(np.max(values) - np.min(values))
        centered = values - np.mean(values)
        spectrum = np.fft.rfft(centered)
        frequencies = np.fft.rfftfreq(values.size, d=1.0 / sample_rate)
        magnitudes = np.abs(spectrum) / values.size
        valid = frequencies > 0
        if frequency_range is not None:
            valid &= frequencies >= frequency_range[0]
            valid &= frequencies <= frequency_range[1]
        if not np.any(valid):
            dominant_frequency = 0.0
            dominant_magnitude = 0.0
        else:
            valid_indices = np.flatnonzero(valid)
            dominant_index = valid_indices[int(np.argmax(magnitudes[valid]))]
            dominant_frequency = float(frequencies[dominant_index])
            dominant_magnitude = float(magnitudes[dominant_index])
        return {
            "sample_rate": sample_rate,
            "rms": rms,
            "peak": peak,
            "peak_to_peak": peak_to_peak,
            "crest_factor": float(peak / rms) if rms else 0.0,
            "dominant_frequency": dominant_frequency,
            "dominant_magnitude": dominant_magnitude,
            "analysis_frequency_range": frequency_range,
        }

    def _extract_model_sensor(self, samples, sample_rate):
        """Match the feature contract used by the saved PyCaret pipelines."""
        np = self._np
        values = preprocess_samples(samples)
        if values.ndim != 1 or values.size < 2:
            raise ValueError(
                "model samples must be a one-dimensional sequence with at least two values"
            )
        if not np.all(np.isfinite(values)):
            raise ValueError("model samples must contain only finite values")

        mean = float(np.mean(values))
        standard_deviation = float(np.std(values))
        rms = float(sqrt(float(np.mean(values * values))))
        maximum = float(np.max(values))
        minimum = float(np.min(values))
        peak = float(np.max(np.abs(values)))
        peak_to_peak = float(np.ptp(values))
        crest_factor = float(peak / rms) if rms > np.finfo(float).eps else 0.0

        centered = values - mean
        window = np.hanning(values.size)
        gain = float(np.mean(window))
        if gain <= np.finfo(float).eps:
            window = np.ones(values.size)
            gain = 1.0
        spectrum = np.fft.rfft(centered * window)
        amplitudes = np.abs(spectrum) * 2.0 / (values.size * gain)
        amplitudes[0] /= 2.0
        if values.size % 2 == 0:
            amplitudes[-1] /= 2.0
        frequencies = np.fft.rfftfreq(values.size, 1.0 / sample_rate)
        first_non_dc = 1 if amplitudes.size > 1 else 0
        dominant_index = first_non_dc + int(np.argmax(amplitudes[first_non_dc:]))

        feature_values = {
            "mean": mean,
            "standard_deviation": standard_deviation,
            "rms": rms,
            "maximum": maximum,
            "minimum": minimum,
            "peak": peak,
            "peak_to_peak": peak_to_peak,
            "crest_factor": crest_factor,
            "dominant_frequency": float(frequencies[dominant_index]),
            "dominant_amplitude": float(amplitudes[dominant_index]),
            "spectral_energy": float(np.sum(np.square(amplitudes))),
        }
        return {name: feature_values[name] for name in MODEL_FEATURE_NAMES}


class NormalBaseline:
    """Calculate a normal-only mean baseline without inventing thresholds."""

    def __init__(self, feature_names):
        self._feature_names = tuple(feature_names)

    def calculate(self, normal_feature_sets):
        feature_sets = list(normal_feature_sets)
        if not feature_sets:
            raise ValueError("at least one normal feature set is required")
        baseline = {}
        for name in self._feature_names:
            values = [features[name] for features in feature_sets]
            baseline[name] = sum(values) / len(values)
        return baseline


class ConditionEvaluator:
    """Compare a Cycle only when externally supplied condition criteria exist."""

    def __init__(
        self, normal_baseline=None, allowed_deviation=None, damaged_baseline=None
    ):
        self._normal_baseline = normal_baseline
        self._allowed_deviation = allowed_deviation
        self._damaged_baseline = damaged_baseline

    def evaluate(self, features):
        if self._normal_baseline is None or self._allowed_deviation is None:
            return {"prediction": None, "leakage_score": None, "ready": False}
        deviations = []
        for name, tolerance in self._allowed_deviation.items():
            if tolerance <= 0:
                raise ValueError("allowed deviations must be positive")
            deviations.append(
                abs(features[name] - self._normal_baseline[name]) / tolerance
            )
        prediction = (
            "ABNORMAL" if any(value > 1.0 for value in deviations) else "NORMAL"
        )
        return {
            "prediction": prediction,
            "leakage_score": self._leakage_score(features),
            "ready": True,
        }

    def _leakage_score(self, features):
        if self._damaged_baseline is None:
            return None
        values = []
        for name, normal_value in self._normal_baseline.items():
            if name not in self._damaged_baseline or name not in features:
                continue
            denominator = self._damaged_baseline[name] - normal_value
            if denominator:
                values.append((features[name] - normal_value) / denominator * 100.0)
        return sum(values) / len(values) if values else None


def make_backend_result(
    cylinder_id,
    session_id,
    cycle_id,
    timestamp,
    features,
    condition,
):
    """Create the existing Backend API payload without overriding ground truth."""
    if condition.get("prediction") not in ("NORMAL", "ABNORMAL"):
        raise RuntimeError("condition criteria are required before Backend submission")
    result = {
        "cylinder_id": cylinder_id,
        "session_id": session_id,
        "cycle_id": cycle_id,
        "timestamp": timestamp,
        "features": features,
        "prediction": condition["prediction"],
    }
    if condition.get("leakage_score") is not None:
        result["leakage_score"] = condition["leakage_score"]
    return result
