"""Read-only terminal monitor for Pico MQTT communication and sensor chunks."""

import argparse
import base64
import json
import os
import struct
import sys
import threading
import time
from datetime import datetime

from .message_parser import ALLOWED_CYLINDER_IDS
from .subscriber import MqttSubscriber

try:
    from system.ML.Condition.analysis import CycleFeatureExtractor
except ImportError:
    CycleFeatureExtractor = None


SENSOR_TOPIC = "smart-cylinder/+/sensor"
STATUS_TOPIC = "cylinder/status/+"
PICO_BY_CYLINDER = {
    "cylinder_%02d" % number: "pico%02d" % number for number in range(1, 7)
}
EXPECTED_RATES = {"sph0645": 4000, "inmp441": 16000}


class Ansi:
    RESET = "\033[0m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    CYAN = "\033[36m"


class PicoStatusMonitor:
    """Maintain and render read-only state for all six Pico publishers."""

    def __init__(
        self,
        wait_after=2.0,
        offline_after=5.0,
        feature_extractor=None,
        clock=time.monotonic,
        use_color=True,
    ):
        if wait_after <= 0 or offline_after <= wait_after:
            raise ValueError("thresholds must satisfy 0 < wait_after < offline_after")
        self.wait_after = float(wait_after)
        self.offline_after = float(offline_after)
        self._clock = clock
        self._feature_extractor = feature_extractor
        self._use_color = use_color
        self._lock = threading.Lock()
        self._broker_connected = False
        self._connection_detail = "STARTING"
        self._subscription_status = "WAITING"
        self._last_topic = None
        self._last_error = None
        self._sensor_topic_messages = 0
        self._status_topic_messages = 0
        self._total_messages = 0
        self._invalid_messages = 0
        self._duplicate_messages = 0
        self._states = {
            cylinder_id: self._empty_state() for cylinder_id in ALLOWED_CYLINDER_IDS
        }
        self._subscriber = MqttSubscriber(lambda _payload, _duplicate: None)

    @staticmethod
    def _empty_state():
        return {
            "last_seen": None,
            "session_id": None,
            "sequence_id": None,
            "sequence_status": "-",
            "sph0645": None,
            "inmp441": None,
            "features": None,
            "reported_status": None,
        }

    def handle_status_message(self, topic, raw_payload):
        """Record a retained Pico Will/online status message."""
        prefix = "cylinder/status/"
        if not isinstance(topic, str) or not topic.startswith(prefix):
            return False
        cylinder_id = topic[len(prefix) :]
        if cylinder_id not in self._states:
            return False
        if isinstance(raw_payload, bytes):
            raw_payload = raw_payload.decode("utf-8")
        status = raw_payload.strip().lower()
        if status not in ("ok", "failed"):
            return False
        with self._lock:
            self._states[cylinder_id]["reported_status"] = status
        return True

    def record_received_topic(self, topic):
        """Record transport activity before parsing the message body."""
        with self._lock:
            self._last_topic = str(topic)
            if str(topic).startswith("cylinder/status/"):
                self._status_topic_messages += 1
            elif str(topic).startswith("smart-cylinder/"):
                self._sensor_topic_messages += 1

    def set_broker_connected(self, connected, detail=None):
        with self._lock:
            self._broker_connected = bool(connected)
            if detail is not None:
                self._connection_detail = str(detail)

    def set_subscription_status(self, status):
        with self._lock:
            self._subscription_status = str(status)

    def handle_message(self, raw_payload):
        """Parse, deduplicate, and record one broker message without forwarding it."""
        with self._lock:
            self._total_messages += 1
        try:
            payload, is_duplicate = self._subscriber.handle_message(raw_payload)
        except (
            TypeError,
            ValueError,
            UnicodeError,
            json.JSONDecodeError,
        ) as error:
            self._record_invalid_rate(raw_payload)
            with self._lock:
                self._invalid_messages += 1
                self._last_error = "%s: %s" % (type(error).__name__, error)
            return None
        self._record_valid(payload, is_duplicate)
        return payload, is_duplicate

    def _record_valid(self, payload, is_duplicate):
        now = self._clock()
        features = self._extract_features(payload)
        cylinder_id = payload["cylinder_id"]
        with self._lock:
            state = self._states[cylinder_id]
            sequence_status = self._classify_sequence(state, payload, is_duplicate)
            state.update(
                {
                    "last_seen": now,
                    "session_id": payload["session_id"],
                    "sequence_id": payload["sequence_id"],
                    "sequence_status": sequence_status,
                    "sph0645": self._sensor_summary(payload["sph0645"]),
                    "inmp441": self._sensor_summary(payload["inmp441"]),
                    "features": features,
                }
            )
            if is_duplicate:
                self._duplicate_messages += 1

    @staticmethod
    def _classify_sequence(state, payload, is_duplicate):
        if is_duplicate:
            return "DUPLICATE"
        previous_session = state["session_id"]
        previous_sequence = state["sequence_id"]
        if previous_sequence is None or previous_session != payload["session_id"]:
            return "NEW SESSION"
        difference = payload["sequence_id"] - previous_sequence
        if difference == 1:
            return "OK"
        if difference > 1:
            return "GAP +%d" % (difference - 1)
        return "OUT OF ORDER"

    @staticmethod
    def _sensor_summary(chunk):
        return {
            "sample_rate": chunk["sample_rate"],
            "sample_count": chunk["sample_count"],
            "rate_status": "OK",
        }

    def _extract_features(self, payload):
        if self._feature_extractor is None:
            return None
        try:
            return self._feature_extractor.extract(
                payload["sph0645"]["samples"], payload["inmp441"]["samples"]
            )
        except (TypeError, ValueError, RuntimeError):
            return None

    def _record_invalid_rate(self, raw_payload):
        """Preserve parser authority while exposing a safe BAD RATE diagnostic."""
        try:
            if isinstance(raw_payload, bytes):
                raw_payload = raw_payload.decode("utf-8")
            payload = (
                json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
            )
            cylinder_id = payload.get("cylinder_id")
            if cylinder_id not in self._states:
                return
            warnings = {}
            for sensor_name, expected_rate in EXPECTED_RATES.items():
                chunk = payload.get(sensor_name)
                if (
                    isinstance(chunk, dict)
                    and chunk.get("sample_rate") != expected_rate
                ):
                    warnings[sensor_name] = {
                        "sample_rate": chunk.get("sample_rate"),
                        "sample_count": chunk.get("sample_count"),
                        "rate_status": "BAD RATE",
                    }
            if warnings:
                with self._lock:
                    self._states[cylinder_id].update(warnings)
        except (
            AttributeError,
            TypeError,
            ValueError,
            UnicodeError,
            json.JSONDecodeError,
        ):
            return

    def communication_status(self, cylinder_id, now=None):
        now = self._clock() if now is None else now
        with self._lock:
            broker_connected = self._broker_connected
            last_seen = self._states[cylinder_id]["last_seen"]
            reported_status = self._states[cylinder_id]["reported_status"]
        if not broker_connected:
            return "BROKER DOWN"
        if reported_status == "failed":
            return "OFFLINE"
        if last_seen is None:
            return "ONLINE" if reported_status == "ok" else "NO DATA"
        age = max(0.0, now - last_seen)
        if age < self.wait_after:
            return "OK"
        if age < self.offline_after:
            return "WAIT"
        return "OFFLINE"

    def snapshot(self, now=None):
        now = self._clock() if now is None else now
        with self._lock:
            states = {
                cylinder_id: {
                    key: value.copy() if isinstance(value, dict) else value
                    for key, value in state.items()
                }
                for cylinder_id, state in self._states.items()
            }
            broker_connected = self._broker_connected
            diagnostics = {
                "connection_detail": self._connection_detail,
                "subscription_status": self._subscription_status,
                "last_topic": self._last_topic,
                "last_error": self._last_error,
                "sensor_topic_messages": self._sensor_topic_messages,
                "status_topic_messages": self._status_topic_messages,
            }
            totals = (
                self._total_messages,
                self._invalid_messages,
                self._duplicate_messages,
            )
        for cylinder_id, state in states.items():
            state["communication_status"] = self._status_from_snapshot(
                broker_connected,
                state["reported_status"],
                state["last_seen"],
                now,
            )
            state["age"] = (
                None
                if state["last_seen"] is None
                else max(0.0, now - state["last_seen"])
            )
        return {
            "broker_connected": broker_connected,
            "states": states,
            "total_messages": totals[0],
            "invalid_messages": totals[1],
            "duplicate_messages": totals[2],
            "diagnostics": diagnostics,
        }

    def _status_from_snapshot(self, broker_connected, reported_status, last_seen, now):
        if not broker_connected:
            return "BROKER DOWN"
        if reported_status == "failed":
            return "OFFLINE"
        if last_seen is None:
            return "ONLINE" if reported_status == "ok" else "NO DATA"
        age = max(0.0, now - last_seen)
        if age < self.wait_after:
            return "OK"
        if age < self.offline_after:
            return "WAIT"
        return "OFFLINE"

    def _colored(self, text, color):
        if not self._use_color:
            return text
        return "%s%s%s" % (color, text, Ansi.RESET)

    def _status_text(self, status):
        if status in ("OK", "ONLINE"):
            return self._colored(status, Ansi.GREEN)
        if status in ("WAIT", "NO DATA"):
            return self._colored(status, Ansi.YELLOW)
        return self._colored(status, Ansi.RED)

    @staticmethod
    def _feature_text(value):
        return "-" if value is None else "%.2f" % value

    def render(self, now=None):
        data = self.snapshot(now)
        lines = ["SMART CYLINDER - PICO MONITOR", ""]
        lines.append("PICO    CYLINDER      MQTT         LAST RX     SEQ      SEQUENCE")
        for cylinder_id, state in data["states"].items():
            age = "never" if state["age"] is None else "%.1fs ago" % state["age"]
            sequence = (
                "-" if state["sequence_id"] is None else str(state["sequence_id"])
            )
            lines.append(
                "%-7s %-13s %-12s %-11s %-8s %s"
                % (
                    PICO_BY_CYLINDER[cylinder_id],
                    cylinder_id,
                    self._status_text(state["communication_status"]),
                    age,
                    sequence,
                    state["sequence_status"],
                )
            )
            lines.append(self._sensor_line("  SPH0645", state, "sph0645"))
            lines.append(self._sensor_line("  INMP441", state, "inmp441"))
        broker_status = "CONNECTED" if data["broker_connected"] else "DISCONNECTED"
        broker_color = Ansi.GREEN if data["broker_connected"] else Ansi.RED
        lines.extend(
            [
                "",
                "Broker: %s" % self._colored(broker_status, broker_color),
                "Connection: %s" % data["diagnostics"]["connection_detail"],
                "Subscriptions: %s" % data["diagnostics"]["subscription_status"],
                "Received Topics: sensor=%d status=%d"
                % (
                    data["diagnostics"]["sensor_topic_messages"],
                    data["diagnostics"]["status_topic_messages"],
                ),
                "Last Topic: %s" % (data["diagnostics"]["last_topic"] or "never"),
                "Last Parse Error: %s" % (data["diagnostics"]["last_error"] or "none"),
                "Total Messages: %d   Invalid Messages: %d   Duplicate Messages: %d"
                % (
                    data["total_messages"],
                    data["invalid_messages"],
                    data["duplicate_messages"],
                ),
                "Update Time: %s"
                % datetime.now().astimezone().isoformat(timespec="seconds"),
            ]
        )
        return "\n".join(lines)

    def _sensor_line(self, label, state, sensor_name):
        sensor = state[sensor_name]
        if sensor is None:
            return "%s rate=- count=- status=NO DATA features=NOT AVAILABLE" % label
        rate_status = sensor["rate_status"]
        status_text = (
            self._colored(rate_status, Ansi.RED)
            if rate_status == "BAD RATE"
            else self._colored(rate_status, Ansi.GREEN)
        )
        features = state["features"]
        if features is None:
            feature_text = "features=NOT AVAILABLE"
        elif sensor_name == "sph0645":
            feature_text = "RMS=%s Peak=%s Dominant=%sHz" % (
                self._feature_text(features.get("sph0645_rms")),
                self._feature_text(features.get("sph0645_peak")),
                self._feature_text(
                    features.get("fft_features", {})
                    .get("sph0645", {})
                    .get("dominant_frequency")
                ),
            )
        else:
            feature_text = "RMS=%s Peak=%s" % (
                self._feature_text(features.get("inmp441_rms")),
                self._feature_text(features.get("inmp441_peak")),
            )
        return "%s rate=%s count=%s status=%s %s" % (
            label,
            sensor.get("sample_rate", "-"),
            sensor.get("sample_count", "-"),
            status_text,
            feature_text,
        )


def _create_feature_extractor():
    if CycleFeatureExtractor is None:
        return None
    try:
        return CycleFeatureExtractor()
    except RuntimeError:
        return None


def _create_paho_client():
    try:
        import paho.mqtt.client as mqtt
    except ImportError as error:
        raise RuntimeError("paho-mqtt is required to run the monitor") from error
    try:
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id="pi-subscriber")
    except (AttributeError, TypeError):
        return mqtt.Client(client_id="pi-subscriber")


def run_monitor(args):
    if not args.username or not args.password:
        raise RuntimeError("MQTT username and password must be provided externally")
    monitor = PicoStatusMonitor(
        wait_after=args.wait_after,
        offline_after=args.offline_after,
        feature_extractor=_create_feature_extractor(),
        use_color=not args.no_color,
    )
    mqtt_client = _create_paho_client()
    mqtt_client.username_pw_set(args.username, args.password)

    def on_connect(_client, _userdata, _flags, reason_code, _properties=None):
        connected = reason_code == 0 or str(reason_code).lower() == "success"
        monitor.set_broker_connected(
            connected,
            (
                "CONNECTED (%s)" % reason_code
                if connected
                else "CONNECT FAILED (%s)" % reason_code
            ),
        )
        if connected:
            sensor_result = mqtt_client.subscribe(SENSOR_TOPIC, qos=1)
            status_result = mqtt_client.subscribe(STATUS_TOPIC, qos=1)
            sensor_code = sensor_result[0]
            status_code = status_result[0]
            if sensor_code == 0 and status_code == 0:
                monitor.set_subscription_status(
                    "REQUESTED sensor=%s status=%s"
                    % (sensor_result[1], status_result[1])
                )
            else:
                monitor.set_subscription_status(
                    "FAILED sensor_rc=%s status_rc=%s" % (sensor_code, status_code)
                )

    def on_disconnect(_client, _userdata, *callback_values):
        reason = callback_values[-1] if callback_values else "unknown"
        monitor.set_broker_connected(False, "DISCONNECTED (%s)" % reason)

    def on_subscribe(_client, _userdata, message_id, *unused):
        monitor.set_subscription_status("ACKNOWLEDGED mid=%s" % message_id)

    mqtt_client.on_connect = on_connect
    mqtt_client.on_disconnect = on_disconnect
    mqtt_client.on_subscribe = on_subscribe

    def on_message(_client, _userdata, message):
        monitor.record_received_topic(message.topic)
        if message.topic.startswith("cylinder/status/"):
            monitor.handle_status_message(message.topic, message.payload)
            return
        monitor.handle_message(message.payload)

    mqtt_client.on_message = on_message
    mqtt_client.connect(
        args.broker_host,
        args.broker_port,
        args.keepalive,
    )
    next_render = 0.0
    next_reconnect = 0.0
    try:
        while True:
            loop_result = mqtt_client.loop(timeout=0.25)
            now = time.monotonic()
            if loop_result != 0:
                monitor.set_broker_connected(
                    False,
                    "NETWORK LOOP ERROR (%s)" % loop_result,
                )
                if now >= next_reconnect:
                    next_reconnect = now + 2.0
                    try:
                        mqtt_client.reconnect()
                    except (OSError, RuntimeError, ValueError) as error:
                        monitor.set_broker_connected(
                            False,
                            "RECONNECT WAIT (%s)" % type(error).__name__,
                        )
            if now >= next_render:
                sys.stdout.write("\033[2J\033[H" + monitor.render(now) + "\n")
                sys.stdout.flush()
                next_render = now + args.refresh_interval
    except KeyboardInterrupt:
        pass
    finally:
        monitor.set_broker_connected(False)
        mqtt_client.disconnect()
        if args.no_color is False:
            sys.stdout.write(Ansi.RESET)
        sys.stdout.write("\n")
        sys.stdout.flush()


def _mock_payload(cylinder_id="cylinder_01", sequence_id=1, sph_rate=4000):
    samples = (100, -100, 200, -200)
    encoded = base64.b64encode(struct.pack("<4i", *samples)).decode("ascii")
    return json.dumps(
        {
            "cylinder_id": cylinder_id,
            "session_id": "12345678-1234-4123-8123-123456789abc",
            "sequence_id": sequence_id,
            "timestamp": "2026-09-27T22:00:00+09:00",
            "sph0645": {
                "sample_rate": sph_rate,
                "sample_format": "s32le",
                "sample_count": 4,
                "encoding": "base64",
                "data": encoded,
            },
            "inmp441": {
                "sample_rate": 16000,
                "sample_format": "s32le",
                "sample_count": 4,
                "encoding": "base64",
                "data": encoded,
            },
        }
    )


def run_mock_checks():
    now = [100.0]
    feature_extractor = _create_feature_extractor()
    monitor = PicoStatusMonitor(
        clock=lambda: now[0],
        use_color=False,
        feature_extractor=feature_extractor,
    )
    monitor.set_broker_connected(True)
    monitor.set_subscription_status("ACKNOWLEDGED mid=1")
    monitor.record_received_topic("smart-cylinder/cylinder_01/sensor")
    monitor.handle_message(_mock_payload())
    assert monitor.communication_status("cylinder_01") == "OK"
    assert monitor.communication_status("cylinder_02") == "NO DATA"
    assert monitor.handle_status_message("cylinder/status/cylinder_02", b"failed")
    assert monitor.communication_status("cylinder_02") == "OFFLINE"
    assert monitor.handle_status_message("cylinder/status/cylinder_02", b"ok")
    assert monitor.communication_status("cylinder_02") == "ONLINE"
    assert monitor.snapshot()["states"]["cylinder_01"]["sph0645"]["sample_rate"] == 4000
    assert monitor.snapshot()["diagnostics"]["sensor_topic_messages"] == 1
    assert monitor.snapshot()["diagnostics"]["subscription_status"].startswith(
        "ACKNOWLEDGED"
    )
    if feature_extractor is not None:
        features = monitor.snapshot()["states"]["cylinder_01"]["features"]
        assert features["sph0645_rms"] > 0
        assert features["sph0645_peak"] == 200.0
        assert features["inmp441_rms"] > 0
        assert features["inmp441_peak"] == 200.0
        assert "dominant_frequency" in features["fft_features"]["sph0645"]
    monitor.handle_message(_mock_payload(sequence_id=2))
    assert monitor.snapshot()["states"]["cylinder_01"]["sequence_status"] == "OK"
    monitor.handle_message(_mock_payload(sequence_id=2))
    assert monitor.snapshot()["states"]["cylinder_01"]["sequence_status"] == "DUPLICATE"
    assert monitor.snapshot()["duplicate_messages"] == 1
    monitor.handle_message(_mock_payload(cylinder_id="cylinder_03", sph_rate=1600))
    assert (
        monitor.snapshot()["states"]["cylinder_03"]["sph0645"]["rate_status"]
        == "BAD RATE"
    )
    assert monitor.snapshot()["invalid_messages"] == 1
    now[0] = 106.0
    assert monitor.communication_status("cylinder_01") == "OFFLINE"
    assert "pico06" in monitor.render()
    print("MOCK PASS")


def build_argument_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--broker-host", default="127.0.0.1")
    parser.add_argument("--broker-port", type=int, default=1883)
    parser.add_argument("--keepalive", type=int, default=60)
    parser.add_argument("--username", default=os.getenv("PICO_MONITOR_MQTT_USERNAME"))
    parser.add_argument("--password", default=os.getenv("PICO_MONITOR_MQTT_PASSWORD"))
    parser.add_argument("--wait-after", type=float, default=2.0)
    parser.add_argument("--offline-after", type=float, default=5.0)
    parser.add_argument("--refresh-interval", type=float, default=1.0)
    parser.add_argument("--no-color", action="store_true")
    parser.add_argument("--mock", action="store_true")
    return parser


def main(argv=None):
    args = build_argument_parser().parse_args(argv)
    if args.mock:
        run_mock_checks()
        return 0
    run_monitor(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
