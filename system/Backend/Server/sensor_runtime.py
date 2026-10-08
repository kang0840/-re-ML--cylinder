"""Pi orchestration; signal processing remains in the injected ML interface."""

import argparse
import importlib
import os
import threading
import logging
import time
from datetime import datetime, timezone
from queue import Queue, Empty, Full
from copy import deepcopy
from dataclasses import dataclass
from collections import OrderedDict, deque

from system.MQTT.subscriber import DuplicateTracker, MqttSubscriber
from system.MQTT.message_parser import parse_payload
from system.Sensor.cycle_detector import CycleChunkBuffer, CycleProcessingCoordinator
from system.ML.Condition.analysis import (
    CycleFeatureExtractor,
    make_backend_result,
    calculate_stft,
    WebPreviewConfig,
    reduce_stft_preview,
    preprocess_samples,
    PREPROCESSING_VERSION,
    make_packet_metrics,
)

LOGGER = logging.getLogger(__name__)


class SensorSampleBuffer:
    """Bounded rolling PCM; origin indexes are not absolute wall-clock times."""

    def __init__(self, config, session, now):
        self.session = session
        self.sequence = None
        self.updated_at = now
        self.timestamp = None
        self.samples = {
            "sph0645": deque(maxlen=config.sph0645_max_samples),
            "inmp441": deque(maxlen=config.inmp441_max_samples),
        }
        self.start_indexes = {"sph0645": 0, "inmp441": 0}

    def append(self, payload, now):
        trimmed = 0
        for sensor, target in self.samples.items():
            values = payload[sensor]["samples"]
            removed = max(0, len(target) + len(values) - target.maxlen)
            self.start_indexes[sensor] += removed
            trimmed += removed
            target.extend(values)
        self.sequence = payload["sequence_id"]
        self.timestamp = payload["timestamp"]
        self.updated_at = now
        return trimmed


@dataclass(frozen=True)
class RealtimeConfig:
    """External resource limits; no deployment sizing defaults."""

    queue_max_size: int
    max_payload_bytes: int
    dedup_max_sessions: int
    dedup_ttl_seconds: float
    sph0645_max_samples: int
    inmp441_max_samples: int
    buffer_max_age_seconds: float
    queue_max_age_seconds: float
    shutdown_timeout_seconds: float

    def __post_init__(self):
        import math
        from numbers import Real

        for name in (
            "queue_max_size",
            "max_payload_bytes",
            "dedup_max_sessions",
            "sph0645_max_samples",
            "inmp441_max_samples",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError("CONFIG_REQUIRED: positive integer " + name)
        for name in (
            "dedup_ttl_seconds",
            "buffer_max_age_seconds",
            "queue_max_age_seconds",
            "shutdown_timeout_seconds",
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, Real)
                or not math.isfinite(value)
                or value <= 0
            ):
                raise ValueError("CONFIG_REQUIRED: finite positive " + name)


@dataclass(frozen=True)
class STFTConfig:
    window_size: int
    hop_length: int
    n_fft: int
    window_function: str
    similarity_threshold: float | None = None

    def __post_init__(self):
        for value in (self.window_size, self.hop_length, self.n_fft):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError("STFT sizes must be positive integers")
        if self.hop_length > self.window_size or self.n_fft < self.window_size:
            raise ValueError("inconsistent STFT sizes")
        if not self.window_function:
            raise ValueError("window_function is required")
        from math import isfinite

        if self.similarity_threshold is not None and (
            isinstance(self.similarity_threshold, bool)
            or not isfinite(self.similarity_threshold)
        ):
            raise ValueError("similarity_threshold must be finite")


class StorageDuplicateTracker(DuplicateTracker):
    """Bounded session high-water marks, committed only after raw persistence.

    Same or older sequence numbers in a retained session never reach downstream.
    Active high-water marks for the six allowed cylinders survive cache expiry.
    Retired sessions have a TTL/LRU horizon; repository uniqueness remains the
    cross-restart/expired-retired-session idempotency boundary.
    No PCM arrays are retained. Used under SensorRuntime's analysis lock.
    """

    def __init__(self, config, clock, event):
        self._messages = OrderedDict()
        self._active = {}
        self.config = config
        self.clock = clock
        self.event = event

    def cleanup(self):
        now = self.clock()
        for key, (_, saved_at) in list(self._messages.items()):
            if now - saved_at > self.config.dedup_ttl_seconds:
                del self._messages[key]
                self.event("DEDUP_SESSION_EXPIRED")

    def record(self, payload):
        self.cleanup()
        key = payload["duplicate_key"][:2]
        active = self._active.get(payload["cylinder_id"])
        if active is not None and active[0] == payload["session_id"]:
            return payload["sequence_id"] <= active[1]
        previous = self._messages.get(key)
        # A retained retired session must not replace the current session.
        return previous is not None

    def acknowledge(self, payload):
        key = payload["duplicate_key"][:2]
        self._messages[key] = (payload["sequence_id"], self.clock())
        self._active[payload["cylinder_id"]] = (
            payload["session_id"],
            payload["sequence_id"],
        )
        self._messages.move_to_end(key)
        while len(self._messages) > self.config.dedup_max_sessions:
            self._messages.popitem(last=False)
            self.event("DEDUP_SESSION_EVICTED", True)


class SensorRuntime:
    """Join existing parser, Cycle, ML and Service without making policy choices.

    stft_detector.detect(chunks, config) returns a continuous (start, end)
    interval in seconds, or None. condition_predictor(features, model_features)
    returns the existing NORMAL/ABNORMAL/ready contract. Both are externally
    supplied ML adapters, not implementations in this orchestration module.
    """

    def __init__(
        self,
        service,
        collection_mode,
        detector_factory=None,
        max_cycle_chunks=None,
        stft_config=None,
        stft_detector=None,
        condition_predictor=None,
        feature_extractor=None,
        realtime_config=None,
        clock=time.monotonic,
        stft_callback=None,
        preview_config=None,
        raw_collection_only=False,
        wall_clock=lambda: datetime.now(timezone.utc).isoformat(),
    ):
        from system.Backend.Service.cylinder_result_service import COLLECTION_MODES

        if collection_mode not in COLLECTION_MODES:
            raise ValueError("CONFIG_REQUIRED: COLLECTION_MODE")
        if realtime_config is not None and not isinstance(
            realtime_config, RealtimeConfig
        ):
            raise ValueError("CONFIG_REQUIRED: RealtimeConfig")
        self.service = service
        self.collection_mode = collection_mode
        self.detector_factory = detector_factory
        self.max_cycle_chunks = max_cycle_chunks
        self.stft_config = stft_config
        self.stft_detector = stft_detector
        self.condition_predictor = condition_predictor
        self.extractor = feature_extractor
        self.realtime_config = realtime_config
        self.clock = clock
        self.stft_callback = stft_callback
        self.preview_config = preview_config
        self.raw_collection_only = raw_collection_only
        if preview_config is not None and not isinstance(
            preview_config, WebPreviewConfig
        ):
            raise ValueError("CONFIG_REQUIRED: WebPreviewConfig")
        self.wall_clock = wall_clock
        self._received_wall = None
        self._preview_generated = {}
        self._preview_stored = {}
        self._previews = {}
        self._buffers = {}
        self.latest_stft = {}
        self.buffer_status = {}
        self._latest_timestamps = {}
        self._raw_sequences = {}
        self._discontinuities = set()
        self.analysis_queue = (
            Queue(realtime_config.queue_max_size) if realtime_config else None
        )
        self._worker = None
        self._stopping = threading.Event()
        self._ingress_lock = threading.Lock()
        self._metrics_lock = threading.Lock()
        self.metrics = {}
        self.ingress_status = "CONFIG_REQUIRED" if not realtime_config else "READY"
        self._cycles = {}
        self._sessions = {}
        self._lock = threading.RLock()
        self._tracker = (
            StorageDuplicateTracker(realtime_config, clock, self._event)
            if realtime_config
            else None
        )
        self.subscriber = (
            MqttSubscriber(self._receive, self._tracker) if self._tracker else None
        )
        self.status = "READY" if not self.missing_config else "CONFIG_REQUIRED"
        self.last_error = None
        self.last_result = None

    @property
    def missing_config(self):
        return [
            name
            for name in (
                "realtime_config",
                "detector_factory",
                "max_cycle_chunks",
                "stft_config",
                "stft_detector",
                "condition_predictor",
            )
            if getattr(self, name) is None
        ]

    def handle_message(self, raw_payload, topic=None):
        """Synchronous diagnostic entry; live MQTT uses enqueue_message instead."""
        if (
            self._worker is not None
            and self._worker.is_alive()
            and threading.current_thread() is not self._worker
        ):
            self._event("CONCURRENT_DIAGNOSTIC_REJECTED", True)
            return None
        with self._lock:
            if self.subscriber is None:
                self.status = "CONFIG_REQUIRED"
                return None
            try:
                if topic is not None:
                    parsed = parse_payload(deepcopy(raw_payload))
                    if topic != "smart-cylinder/%s/sensor" % parsed["cylinder_id"]:
                        raise ValueError("topic identity mismatch")
                    raw_payload = parsed
                if self._received_wall is None:
                    self._received_wall = self.wall_clock()
                result = self.subscriber.handle_message(deepcopy(raw_payload))
                if result[1]:
                    self._event("DUPLICATE_OR_OLD_SEQUENCE_IGNORED")
                return result
            except Exception as error:
                self.status = "INPUT_OR_STORAGE_FAILED"
                self.last_error = type(error).__name__
                self._event("INPUT_OR_STORAGE_FAILED", True)
                return None
            finally:
                self._received_wall = None

    def _event(self, name, warning=False):
        with self._metrics_lock:
            self.metrics[name] = self.metrics.get(name, 0) + 1
        (LOGGER.warning if warning else LOGGER.info)(name)

    def enqueue_message(self, raw_payload, topic=None):
        """Bound wire bytes and enqueue without waiting for analysis or storage.

        Return value is local acceptance only, not a persistence acknowledgement.
        QoS 1 transport acknowledgement does not guarantee queue/storage success.
        """
        if self.analysis_queue is None:
            self.ingress_status = "CONFIG_REQUIRED"
            self._event("INGRESS_CONFIG_REQUIRED", True)
            return False
        if not isinstance(raw_payload, (bytes, str)):
            self._event("INVALID_WIRE_PAYLOAD", True)
            return False
        if len(raw_payload) > self.realtime_config.max_payload_bytes:
            self._event("PAYLOAD_TOO_LARGE", True)
            return False
        try:
            wire = (
                raw_payload.encode("utf-8")
                if isinstance(raw_payload, str)
                else raw_payload
            )
        except UnicodeEncodeError:
            self._event("INVALID_WIRE_PAYLOAD", True)
            return False
        if len(wire) > self.realtime_config.max_payload_bytes:
            self._event("PAYLOAD_TOO_LARGE", True)
            return False
        if topic is not None and topic not in {
            "smart-cylinder/cylinder_%02d/sensor" % i for i in range(1, 7)
        }:
            self._event("INVALID_TOPIC", True)
            return False
        with self._ingress_lock:
            if self._stopping.is_set():
                self._event("INGRESS_STOPPED", True)
                return False
            try:
                self.analysis_queue.put_nowait(
                    (wire, topic, self.clock(), self.wall_clock())
                )
            except Full:
                self.ingress_status = "QUEUE_OVERFLOW"
                self._discontinuities.update(
                    [topic.split("/")[1]]
                    if topic
                    else ["cylinder_%02d" % i for i in range(1, 7)]
                )
                self._event("QUEUE_OVERFLOW_DROPPED", True)
                return False
        self.ingress_status = "QUEUED"
        self._event("SENSOR_PACKET_QUEUED")
        return True

    def process_next(self):
        """One nonblocking worker iteration, also available for deterministic tests."""
        if self._worker is not None and self._worker.is_alive():
            self._event("CONCURRENT_DIAGNOSTIC_REJECTED", True)
            return False
        if self.analysis_queue is None:
            return False
        try:
            item = self.analysis_queue.get_nowait()
        except Empty:
            self.cleanup()
            return False
        self._process_item(item)
        return True

    def _process_item(self, item):
        try:
            if item is None:
                return
            wire, topic, received_at, received_wall = item
            if (
                not self.raw_collection_only
                and self.clock() - received_at
                > self.realtime_config.queue_max_age_seconds
            ):
                with self._ingress_lock:
                    self._discontinuities.update(
                        [topic.split("/")[1]]
                        if topic
                        else ["cylinder_%02d" % i for i in range(1, 7)]
                    )
                self._event("QUEUE_STALE_DROPPED", True)
                return
            self._received_wall = received_wall
            self.handle_message(wire, topic)
        except Exception as error:
            self.status = "ANALYSIS_ERROR"
            self.last_error = type(error).__name__
            self._event("ANALYSIS_ERROR", True)
        finally:
            self.analysis_queue.task_done()

    def start(self):
        """Start the single ordered analysis consumer, never in the MQTT callback."""
        if self.analysis_queue is None:
            self.status = "CONFIG_REQUIRED"
            return False
        with self._ingress_lock:
            if self._worker is not None and self._worker.is_alive():
                return False
            self._stopping.clear()
            self._worker = threading.Thread(
                target=self._run_worker, name="sensor-analysis", daemon=True
            )
            self._worker.start()
        return True

    def _run_worker(self):
        while not self._stopping.is_set() or (
            self.raw_collection_only and not self.analysis_queue.empty()
        ):
            try:
                item = self.analysis_queue.get(
                    timeout=min(
                        self.realtime_config.buffer_max_age_seconds,
                        self.realtime_config.dedup_ttl_seconds,
                    )
                )
            except Empty:
                self.cleanup()
                continue
            self._process_item(item)

    def cleanup(self):
        """Worker maintenance expires idle PCM and STFT snapshots as well as dedup."""
        with self._lock:
            if self._tracker is not None:
                self._tracker.cleanup()
            now = self.clock()
            for cylinder, buffer in list(self._buffers.items()):
                if (
                    now - buffer.updated_at
                    > self.realtime_config.buffer_max_age_seconds
                ):
                    self._buffers.pop(cylinder)
                    self.latest_stft.pop(cylinder, None)
                    self._cycles.pop(cylinder, None)
                    self.buffer_status[cylinder] = "BUFFER_EXPIRED"
                    self._event("BUFFER_EXPIRED", True)

    def _buffer_payload(self, payload):
        self.cleanup()
        cylinder = payload["cylinder_id"]
        session = payload["session_id"]
        buffer = self._buffers.get(cylinder)
        with self._ingress_lock:
            discontinuity = cylinder in self._discontinuities
            self._discontinuities.discard(cylinder)
        reason = None
        if buffer is not None:
            if session != buffer.session:
                reason = "BUFFER_SESSION_CHANGED"
            elif payload["sequence_id"] != buffer.sequence + 1:
                reason = "BUFFER_SEQUENCE_GAP"
            elif discontinuity:
                reason = "BUFFER_INGRESS_DISCONTINUITY"
        if reason is not None:
            self._cycles.pop(cylinder, None)
            self.latest_stft.pop(cylinder, None)
            self._event(reason, True)
            buffer = None
        if buffer is None:
            buffer = SensorSampleBuffer(self.realtime_config, session, self.clock())
            self._buffers[cylinder] = buffer
        trimmed = buffer.append(payload, self.clock())
        if trimmed:
            self._event("BUFFER_OLD_SAMPLES_TRIMMED")
        self.buffer_status[cylinder] = "BUFFER_READY"
        self._event("SENSOR_PACKET_BUFFERED")

    def _calculate_buffer(self, cylinder):
        """Run the Canonical calculation, never fabricate a motion interval."""
        from collections.abc import Mapping

        buffer = self._buffers[cylinder]
        self.latest_stft.pop(cylinder, None)
        snapshot = {
            "cylinder_id": cylinder,
            "session_id": buffer.session,
            "sequence_id": buffer.sequence,
            "timestamp": buffer.timestamp,
            "received_monotonic": buffer.updated_at,
            "sensors": {},
            "operation_status": "REFERENCE_REQUIRED",
        }
        if self.stft_config is None:
            self.status = "CONFIG_REQUIRED"
            self._event("STFT_CONFIG_REQUIRED", True)
            return False
        try:
            for sensor, rate in (("sph0645", 4000), ("inmp441", 16000)):
                config = self.stft_config
                if isinstance(config, Mapping) and sensor in config:
                    config = config[sensor]
                if any(
                    (
                        config.get(name)
                        if isinstance(config, Mapping)
                        else getattr(config, name, None)
                    )
                    is None
                    for name in (
                        "window_size",
                        "hop_length",
                        "n_fft",
                        "window_function",
                    )
                ):
                    self.status = "CONFIG_REQUIRED"
                    self._event("STFT_CONFIG_REQUIRED", True)
                    return False
                size = (
                    config.get("window_size")
                    if isinstance(config, Mapping)
                    else getattr(config, "window_size", None)
                )
                if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
                    raise ValueError("CONFIG_REQUIRED: window_size")
                if size > buffer.samples[sensor].maxlen:
                    self.status = "CONFIG_REQUIRED"
                    self._event("STFT_WINDOW_EXCEEDS_BUFFER", True)
                    return False
                if len(buffer.samples[sensor]) < size:
                    self.status = "WAITING_SAMPLES"
                    self.buffer_status[cylinder] = "WAITING_SAMPLES"
                    return False
                self._event("STFT_STARTED")
                result = calculate_stft(
                    preprocess_samples(list(buffer.samples[sensor])), rate, config
                )
                snapshot["sensors"][sensor] = {
                    "sample_rate": rate,
                    "sample_start_index": buffer.start_indexes[sensor],
                    "result": result,
                }
                self._event("STFT_COMPLETED")
            self.latest_stft[cylinder] = snapshot
            self.status = "REFERENCE_REQUIRED"
            if self.stft_callback is not None:
                self.stft_callback(snapshot)
            return True
        except Exception as error:
            self.latest_stft.pop(cylinder, None)
            self.status = "ANALYSIS_ERROR"
            self.last_error = type(error).__name__
            self._event("ANALYSIS_ERROR", True)
            return False

    def stop(self):
        """Bounded shutdown; an in-flight external call cannot be forcibly killed."""
        if self.analysis_queue is None:
            return True
        with self._ingress_lock:
            self._stopping.set()
            try:
                self.analysis_queue.put_nowait(None)
            except Full:
                pass
        if self._worker is not None:
            self._worker.join(self.realtime_config.shutdown_timeout_seconds)
            if self._worker.is_alive():
                self._event("WORKER_STOP_TIMEOUT", True)
                return False
        while True:
            try:
                item = self.analysis_queue.get_nowait()
            except Empty:
                break
            self.analysis_queue.task_done()
            if item is not None:
                self._event("SHUTDOWN_DROPPED", True)
        return True

    def _receive(self, payload, is_duplicate):
        from datetime import datetime

        cylinder = payload["cylinder_id"]
        measured_at = datetime.fromisoformat(payload["timestamp"])
        previous = self._latest_timestamps.get(cylinder)
        if previous is not None and measured_at < previous:
            self._event("OUT_OF_ORDER_TIMESTAMP_DROPPED", True)
            return
        try:
            self.service.record_sensor_message(
                payload, is_duplicate=is_duplicate, collection_mode=self.collection_mode
            )
        except Exception:
            LOGGER.warning(
                "PERSISTENCE_GAP cylinder=%s session=%s sequence=%s",
                cylinder,
                payload["session_id"],
                payload["sequence_id"],
            )
            self._event("RAW_STORAGE_ERROR", True)
            raise
        self._tracker.acknowledge(payload)
        self._latest_timestamps[cylinder] = measured_at
        self._event("RAW_STORED")
        self.last_error = None
        if self.raw_collection_only:
            self._log_raw_collection(payload)
            self.status = "RAW_COLLECTION_RUNNING"
            self._store_runtime(payload, False)
            return
        cylinder = payload["cylinder_id"]
        session = payload["session_id"]
        if self._sessions.get(cylinder) != session:
            self._cycles.pop(cylinder, None)
            self._previews.pop(cylinder, None)
            self._preview_generated.pop(cylinder, None)
            self._preview_stored.pop(cylinder, None)
            self._sessions[cylinder] = session
        self._buffer_payload(payload)
        stft_ready = self._calculate_buffer(cylinder)
        self._store_runtime(payload, stft_ready)
        if self.status == "ANALYSIS_ERROR":
            return
        if self.missing_config:
            if not stft_ready and self.status != "WAITING_SAMPLES":
                self.status = "CONFIG_REQUIRED"
            return
        self.status = "READY"
        if cylinder not in self._cycles:
            self._cycles[cylinder] = CycleProcessingCoordinator(
                self.detector_factory(cylinder),
                CycleChunkBuffer(self.max_cycle_chunks),
                self._completed,
            )
        self._cycles[cylinder].receive_sensor_chunk(payload)

    def _log_raw_collection(self, payload):
        """Report collection evidence, not learned thresholds or a quality PASS."""
        import math
        from system.Backend.Service.cylinder_result_service import (
            resolve_collection_route,
        )

        cylinder = payload["cylinder_id"]
        session = payload["session_id"]
        sequence = payload["sequence_id"]
        previous = self._raw_sequences.get(cylinder)
        if (
            previous is not None
            and previous[0] == session
            and sequence > previous[1] + 1
        ):
            self._event("RAW_SEQUENCE_GAP", True)
            LOGGER.warning(
                "RAW_SEQUENCE_GAP cylinder=%s session=%s missing=%s",
                cylinder,
                session,
                sequence - previous[1] - 1,
            )
        self._raw_sequences[cylinder] = (session, sequence)
        route = (
            self.service.resolve_route(self.collection_mode, cylinder)
            if hasattr(self.service, "resolve_route")
            else resolve_collection_route(self.collection_mode, cylinder)
        )
        LOGGER.info(
            "RAW_COLLECTION cylinder=%s session=%s sequence=%s mode=%s ground_truth=%s stored=%s",
            cylinder,
            session,
            sequence,
            self.collection_mode,
            route["ground_truth"],
            self.metrics.get("RAW_STORED", 0),
        )
        for sensor in ("sph0645", "inmp441"):
            samples = payload[sensor]["samples"]
            low, high = min(samples), max(samples)
            LOGGER.info(
                "RAW_QUALITY cylinder=%s sensor=%s count=%s min=%s max=%s mean=%s "
                "finite=%s all_zero=%s constant=%s clipping=DATA_REQUIRED",
                cylinder,
                sensor,
                len(samples),
                low,
                high,
                sum(samples) / len(samples),
                all(math.isfinite(x) for x in samples),
                low == high == 0,
                low == high,
            )
        if payload["sph0645"]["samples"] == payload["inmp441"]["samples"]:
            self._event("SENSOR_ARRAY_EQUAL_CHECK_REQUIRED", True)

    def _store_runtime(self, payload, stft_ready):
        """Persist trusted Pi metadata; never use sender-provided runtime."""
        state = (
            "COMPLETED"
            if stft_ready
            else {
                "WAITING_SAMPLES": "BUFFERING",
                "CONFIG_REQUIRED": "CONFIG_REQUIRED",
                "ANALYSIS_ERROR": "ANALYSIS_ERROR",
            }.get(self.status, "WAITING_FOR_DATA")
        )
        if self.raw_collection_only:
            state = (
                "CONFIG_REQUIRED" if self.stft_config is None else "WAITING_FOR_DATA"
            )
        metadata = dict(
            last_received_at=self._received_wall,
            stft_status=state,
            operation_status="REFERENCE_REQUIRED",
            ml_status=(
                "MODEL_REQUIRED"
                if self.condition_predictor is None
                else "WAITING_FOR_OPERATION"
            ),
            stft_preview=None,
        )
        if self.collection_mode == "OPERATION":
            try:
                metadata["packet_metrics"] = make_packet_metrics(payload)
            except Exception as error:
                self.last_error = type(error).__name__
                self._event("PACKET_METRICS_ERROR", True)
        cylinder = payload["cylinder_id"]
        config = self.preview_config
        now = self.clock()
        if stft_ready and config is not None:
            try:
                if (
                    now - self._preview_generated.get(cylinder, float("-inf"))
                    >= config.generate_interval_seconds
                ):
                    preview = reduce_stft_preview(self.latest_stft[cylinder], config)
                    self._previews[cylinder] = (payload["sequence_id"], preview)
                    self._preview_generated[cylinder] = now
                    self._event("PREVIEW_GENERATED")
                cached = self._previews.get(cylinder)
                # Do not attach an old matrix to the current sequence/time.
                if (
                    cached
                    and cached[0] == payload["sequence_id"]
                    and now - self._preview_stored.get(cylinder, float("-inf"))
                    >= config.store_interval_seconds
                ):
                    metadata["stft_preview"] = cached[1]
            except Exception as error:
                self.last_error = type(error).__name__
                self._event("PREVIEW_ERROR", True)
        elif config is None:
            self._event("PREVIEW_CONFIG_REQUIRED")
        try:
            self.service.record_runtime(
                payload, metadata, config.keep_rows if config else None
            )
            if metadata["stft_preview"] is not None:
                self._preview_stored[cylinder] = now
            self._event("RUNTIME_STORED")
            if "packet_metrics" in metadata:
                self._event("PACKET_METRICS_STORED")
        except Exception as error:
            self.last_error = type(error).__name__
            self._event("RUNTIME_STORAGE_ERROR", True)

    def update_distances(self, cylinder_id, distances_cm):
        with self._lock:
            if cylinder_id not in self._cycles:
                return []
            try:
                return self._cycles[cylinder_id].update_distances(distances_cm)
            except Exception as error:
                self.status = "CYCLE_FAILED"
                self.last_error = type(error).__name__
                return []

    def _completed(self, cycle_id, chunks, reason):
        if reason != "completed" or not chunks:
            self.status = "CYCLE_INCOMPLETE"
            return
        if (
            getattr(self.condition_predictor, "preprocessing_version", None)
            != PREPROCESSING_VERSION
        ):
            self.status = "MODEL_REQUIRED"
            return
        identities = {(p["cylinder_id"], p["session_id"]) for p in chunks}
        sequences = [p["sequence_id"] for p in chunks]
        if len(identities) != 1 or any(
            b != a + 1 for a, b in zip(sequences, sequences[1:])
        ):
            self.status = "CYCLE_INCOMPLETE"
            return
        interval = self.stft_detector.detect(chunks, self.stft_config)
        if interval is None:
            self.status = "NO_MOTION_SOUND"
            return
        import math

        start, end = interval
        if not all(math.isfinite(v) for v in interval) or start < 0 or end <= start:
            raise ValueError("invalid STFT interval")
        samples = {}
        for sensor, rate in (("sph0645", 4000), ("inmp441", 16000)):
            values = [s for p in chunks for s in p[sensor]["samples"]]
            if end > len(values) / rate:
                raise ValueError("STFT interval exceeds captured audio")
            selected = values[math.ceil(start * rate) : math.floor(end * rate)]
            if len(selected) < 2:
                raise ValueError("STFT interval has insufficient samples")
            samples[sensor] = selected
        extractor = self.extractor or CycleFeatureExtractor()
        model_features = extractor.extract_model_features(
            samples["sph0645"], samples["inmp441"]
        )
        features = extractor.extract(samples["sph0645"], samples["inmp441"])
        condition = self.condition_predictor(features, model_features)
        if not condition.get("ready", False):
            self.status = "MODEL_REQUIRED"
            return
        first = chunks[0]
        result = make_backend_result(
            first["cylinder_id"],
            first["session_id"],
            cycle_id,
            first["timestamp"],
            features,
            condition,
        )
        self.service.record_cycle_result(result)
        self.last_result = result
        self.status = "STORED"


def main():
    """Use an existing external factory for policies and HC-SR04 scheduling."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--factory", help="trusted installed module:function")
    args = parser.parse_args()
    if not args.factory or not os.environ.get("COLLECTION_MODE"):
        print("CONFIG_REQUIRED: --factory and COLLECTION_MODE")
        return 2
    module, name = args.factory.split(":", 1)
    runtime = getattr(importlib.import_module(module), name)()
    if runtime.realtime_config is None:
        print("CONFIG_REQUIRED: realtime_config")
        return 2
    from system.MQTT.client import PiMqttClient
    import paho.mqtt.client as mqtt

    password = os.environ.get("MQTT_PASSWORD")
    if not password:
        print("CONFIG_REQUIRED: MQTT_PASSWORD")
        return 2
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    connection = PiMqttClient(client, subscriber=runtime, password=password)

    def on_connect(_client, _userdata, _flags, reason, _properties):
        if reason == 0:
            connection.on_reconnect()

    client.on_connect = on_connect
    logging.basicConfig(level=logging.INFO)
    runtime.start()
    try:
        connection.connect_and_subscribe()
        client.loop_forever()
    finally:
        try:
            client.disconnect()
        finally:
            runtime.stop()


if __name__ == "__main__":
    raise SystemExit(main())
