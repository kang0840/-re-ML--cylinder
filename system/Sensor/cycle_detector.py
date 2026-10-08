"""Parameterized HC-SR04 cycle state and active-cycle chunk buffering."""

from uuid import uuid4

STOP = "STOP"
FORWARD = "FORWARD"
RETURN = "RETURN"
VALID_STATES = (STOP, FORWARD, RETURN)


class CycleDetector:
    """Turn externally resolved motion states into Cycle start/end events."""

    def __init__(
        self,
        state_resolver,
        confirmations_required,
        max_cycle_seconds,
        clock,
        cycle_id_factory=uuid4,
    ):
        if confirmations_required < 1:
            raise ValueError("confirmations_required must be at least one")
        if max_cycle_seconds <= 0:
            raise ValueError("max_cycle_seconds must be positive")
        self._state_resolver = state_resolver
        self._confirmations_required = confirmations_required
        self._max_cycle_seconds = max_cycle_seconds
        self._clock = clock
        self._cycle_id_factory = cycle_id_factory
        self._stable_state = STOP
        self._candidate_state = None
        self._candidate_count = 0
        self._cycle_id = None
        self._cycle_started_at = None
        self._has_returned = False

    @property
    def active_cycle_id(self):
        return self._cycle_id

    def update(self, distances_cm):
        """Return zero or more start/end events for a three-sensor reading."""
        resolved_state = self._state_resolver(distances_cm)
        if resolved_state not in VALID_STATES:
            raise ValueError("state_resolver must return STOP, FORWARD, or RETURN")
        events = self._expire_if_needed()
        if resolved_state != self._candidate_state:
            self._candidate_state = resolved_state
            self._candidate_count = 1
        else:
            self._candidate_count += 1
        if (
            self._candidate_count < self._confirmations_required
            or resolved_state == self._stable_state
        ):
            return events
        previous_state = self._stable_state
        self._stable_state = resolved_state
        events.extend(self._transition(previous_state, resolved_state))
        return events

    def _transition(self, previous_state, next_state):
        if previous_state == STOP and next_state == FORWARD and self._cycle_id is None:
            self._cycle_id = str(self._cycle_id_factory())
            self._cycle_started_at = self._clock()
            self._has_returned = False
            return [("started", self._cycle_id)]
        if self._cycle_id is not None and next_state == RETURN:
            self._has_returned = True
        if self._cycle_id is not None and next_state == STOP and self._has_returned:
            return [self._finish("completed")]
        return []

    def _expire_if_needed(self):
        if self._cycle_id is None:
            return []
        if self._clock() - self._cycle_started_at <= self._max_cycle_seconds:
            return []
        return [self._finish("expired")]

    def _finish(self, reason):
        event = ("ended", self._cycle_id, reason)
        self._cycle_id = None
        self._cycle_started_at = None
        self._has_returned = False
        return event


class CycleChunkBuffer:
    """Accumulate decoded MQTT chunks only while a detector Cycle is active."""

    def __init__(self, max_cycle_chunks):
        if max_cycle_chunks < 1:
            raise ValueError("max_cycle_chunks must be at least one")
        self._max_cycle_chunks = max_cycle_chunks
        self._cycle_id = None
        self._chunks = []

    def start(self, cycle_id):
        self._cycle_id = cycle_id
        self._chunks = []

    def append(self, payload):
        if self._cycle_id is None:
            return False
        if len(self._chunks) >= self._max_cycle_chunks:
            raise RuntimeError("maximum Cycle chunk count exceeded")
        self._chunks.append(payload)
        return True

    def finish(self, cycle_id):
        if self._cycle_id != cycle_id:
            raise ValueError("Cycle buffer does not match the completed Cycle")
        completed = self._chunks
        self._cycle_id = None
        self._chunks = []
        return completed


class CycleProcessingCoordinator:
    """Join active-Cycle MQTT chunks with externally supplied distance readings."""

    def __init__(self, detector, chunk_buffer, on_cycle_completed):
        self._detector = detector
        self._chunk_buffer = chunk_buffer
        self._on_cycle_completed = on_cycle_completed

    def receive_sensor_chunk(self, payload):
        """Buffer a parser-validated chunk only for an active Cycle."""
        return self._chunk_buffer.append(payload)

    def update_distances(self, distances_cm):
        """Advance Cycle state and submit completed chunks to an injected handler."""
        events = self._detector.update(distances_cm)
        for event in events:
            if event[0] == "started":
                self._chunk_buffer.start(event[1])
            elif event[0] == "ended":
                _, cycle_id, reason = event
                chunks = self._chunk_buffer.finish(cycle_id)
                self._on_cycle_completed(cycle_id, chunks, reason)
        return events
