"""Relay Supabase A/B process events to the Raspberry Pi Mosquitto broker."""

import json
import os
import threading
import time
from datetime import datetime, timedelta, timezone

PROCESS_TOPIC = "smart-cylinder/process/events"
SEOUL_TIMEZONE = timezone(timedelta(hours=9))
DISPATCH_BATCH_SIZE = 20
CLAIM_TIMEOUT_SECONDS = 60


class BridgeConfigurationError(RuntimeError):
    """Raised when a required server-side setting is missing."""


def _now():
    return datetime.now(SEOUL_TIMEZONE)


def _timestamp():
    return _now().isoformat(timespec="seconds")


def _safe_error(error):
    """Return a bounded error message without printing credentials."""
    return f"{type(error).__name__}: {error}"[:300]


class ProcessOrderBridge:
    """Claim each database event once and publish it with a stable event key."""

    def __init__(self, supabase_client, mqtt_client, topic=PROCESS_TOPIC):
        self._supabase = supabase_client
        self._mqtt = mqtt_client
        self._topic = topic

    def poll_once(self):
        """Publish pending start and judgment events, then reconcile completion."""
        self._recover_stale_claims()
        starts = self._pending_orders()
        judgments = self._pending_judgments()
        published_starts = sum(self._dispatch_start(row) for row in starts)
        published_judgments = sum(self._dispatch_judgment(row) for row in judgments)
        self._reconcile_completed_orders()
        return {
            "process_start": published_starts,
            "process_judgment": published_judgments,
        }

    def run_forever(self, poll_interval=2.0):
        """Continue polling until interrupted by the service manager or operator."""
        while True:
            try:
                self.poll_once()
            except Exception as error:
                print(f"Process order bridge poll failed: {_safe_error(error)}")
            time.sleep(poll_interval)

    def _pending_orders(self):
        response = (
            self._supabase.table("process_orders")
            .select(
                "order_id,requested_product,status,start_dispatch_state,"
                "start_dispatch_attempts"
            )
            .in_("status", ["REQUESTED", "FAILED"])
            .in_("start_dispatch_state", ["PENDING", "FAILED"])
            .order("created_at")
            .limit(DISPATCH_BATCH_SIZE)
            .execute()
        )
        return response.data or []

    def _pending_judgments(self):
        response = (
            self._supabase.table("process_judgments")
            .select(
                "order_id,requested_product,detected_product,judgment,"
                "detection_source,dispatch_state,dispatch_attempts"
            )
            .in_("dispatch_state", ["PENDING", "FAILED"])
            .order("created_at")
            .limit(DISPATCH_BATCH_SIZE)
            .execute()
        )
        return response.data or []

    def _dispatch_start(self, row):
        order_id = row["order_id"]
        previous_state = row["start_dispatch_state"]
        claimed = (
            self._supabase.table("process_orders")
            .update(
                {
                    "start_dispatch_state": "PUBLISHING",
                    "start_dispatch_attempts": int(
                        row.get("start_dispatch_attempts") or 0
                    )
                    + 1,
                    "start_claimed_at": _timestamp(),
                    "start_last_error": None,
                }
            )
            .eq("order_id", order_id)
            .eq("start_dispatch_state", previous_state)
            .execute()
        )
        if not claimed.data:
            return 0

        payload = {
            "message_type": "PROCESS_START",
            "event_id": f"{order_id}:PROCESS_START",
            "order_id": order_id,
            "requested_product": row["requested_product"],
            "timestamp": _timestamp(),
        }
        try:
            self._publish(payload)
            published_at = _timestamp()
            (
                self._supabase.table("process_orders")
                .update(
                    {
                        "status": "STARTED",
                        "started_at": published_at,
                        "start_dispatch_state": "PUBLISHED",
                        "start_published_at": published_at,
                        "start_claimed_at": None,
                        "start_last_error": None,
                    }
                )
                .eq("order_id", order_id)
                .eq("start_dispatch_state", "PUBLISHING")
                .execute()
            )
            return 1
        except Exception as error:
            (
                self._supabase.table("process_orders")
                .update(
                    {
                        "status": "FAILED",
                        "start_dispatch_state": "FAILED",
                        "start_claimed_at": None,
                        "start_last_error": _safe_error(error),
                    }
                )
                .eq("order_id", order_id)
                .eq("start_dispatch_state", "PUBLISHING")
                .execute()
            )
            return 0

    def _dispatch_judgment(self, row):
        order_id = row["order_id"]
        previous_state = row["dispatch_state"]
        claimed = (
            self._supabase.table("process_judgments")
            .update(
                {
                    "dispatch_state": "PUBLISHING",
                    "dispatch_attempts": int(row.get("dispatch_attempts") or 0) + 1,
                    "claimed_at": _timestamp(),
                    "last_error": None,
                }
            )
            .eq("order_id", order_id)
            .eq("dispatch_state", previous_state)
            .execute()
        )
        if not claimed.data:
            return 0

        payload = {
            "message_type": "PROCESS_JUDGMENT",
            "event_id": f"{order_id}:PROCESS_JUDGMENT",
            "order_id": order_id,
            "requested_product": row["requested_product"],
            "detected_product": row["detected_product"],
            "judgment": row["judgment"],
            "detection_source": row["detection_source"],
            "timestamp": _timestamp(),
        }
        try:
            self._publish(payload)
            published_at = _timestamp()
            (
                self._supabase.table("process_judgments")
                .update(
                    {
                        "dispatch_state": "PUBLISHED",
                        "published_at": published_at,
                        "claimed_at": None,
                        "last_error": None,
                    }
                )
                .eq("order_id", order_id)
                .eq("dispatch_state", "PUBLISHING")
                .execute()
            )
            return 1
        except Exception as error:
            (
                self._supabase.table("process_judgments")
                .update(
                    {
                        "dispatch_state": "FAILED",
                        "claimed_at": None,
                        "last_error": _safe_error(error),
                    }
                )
                .eq("order_id", order_id)
                .eq("dispatch_state", "PUBLISHING")
                .execute()
            )
            return 0

    def _publish(self, payload):
        encoded = json.dumps(
            payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        )
        info = self._mqtt.publish(
            self._topic,
            encoded,
            qos=1,
            retain=False,
        )
        if getattr(info, "rc", 0) != 0:
            raise RuntimeError(f"MQTT publish failed with code {info.rc}")
        info.wait_for_publish(timeout=10)
        if hasattr(info, "is_published") and not info.is_published():
            raise RuntimeError("MQTT publish acknowledgement timed out")

    def _recover_stale_claims(self):
        cutoff = (_now() - timedelta(seconds=CLAIM_TIMEOUT_SECONDS)).isoformat(
            timespec="seconds"
        )
        (
            self._supabase.table("process_orders")
            .update(
                {
                    "status": "FAILED",
                    "start_dispatch_state": "FAILED",
                    "start_claimed_at": None,
                    "start_last_error": "stale publish claim recovered",
                }
            )
            .eq("start_dispatch_state", "PUBLISHING")
            .lt("start_claimed_at", cutoff)
            .execute()
        )
        (
            self._supabase.table("process_judgments")
            .update(
                {
                    "dispatch_state": "FAILED",
                    "claimed_at": None,
                    "last_error": "stale publish claim recovered",
                }
            )
            .eq("dispatch_state", "PUBLISHING")
            .lt("claimed_at", cutoff)
            .execute()
        )

    def _reconcile_completed_orders(self):
        response = (
            self._supabase.table("process_judgments")
            .select("order_id,published_at")
            .eq("dispatch_state", "PUBLISHED")
            .is_("completion_synced_at", "null")
            .limit(DISPATCH_BATCH_SIZE)
            .execute()
        )
        for row in response.data or []:
            completed_at = row.get("published_at") or _timestamp()
            (
                self._supabase.table("process_orders")
                .update({"status": "COMPLETED", "completed_at": completed_at})
                .eq("order_id", row["order_id"])
                .execute()
            )
            (
                self._supabase.table("process_judgments")
                .update({"completion_synced_at": _timestamp()})
                .eq("order_id", row["order_id"])
                .eq("dispatch_state", "PUBLISHED")
                .execute()
            )


def _required_environment(name, fallback_name=None):
    value = os.environ.get(name, "").strip()
    if not value and fallback_name:
        value = os.environ.get(fallback_name, "").strip()
    if not value:
        raise BridgeConfigurationError(
            f"required environment variable is missing: {name}"
        )
    return value


def _mqtt_client():
    import paho.mqtt.client as mqtt

    connected = threading.Event()
    try:
        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id="pi-process-order-bridge",
        )
    except (AttributeError, TypeError):
        client = mqtt.Client(client_id="pi-process-order-bridge")

    def on_connect(_client, _userdata, _flags, reason_code, _properties=None):
        if int(reason_code) == 0:
            connected.set()

    client.on_connect = on_connect
    client.username_pw_set(
        _required_environment("MQTT_USERNAME"),
        _required_environment("MQTT_PASSWORD"),
    )
    host = os.environ.get("MQTT_BROKER_HOST", "127.0.0.1").strip()
    port = int(os.environ.get("MQTT_BROKER_PORT", "1883"))
    client.connect(host, port, keepalive=60)
    client.loop_start()
    if not connected.wait(timeout=10):
        client.loop_stop()
        raise RuntimeError("MQTT broker connection timed out")
    return client, host, port


def main():
    from supabase import create_client

    supabase_client = create_client(
        _required_environment("SUPABASE_URL"),
        _required_environment("SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_KEY"),
    )
    mqtt_client, host, port = _mqtt_client()
    interval = float(os.environ.get("PROCESS_POLL_INTERVAL", "2"))
    print(f"Process order bridge connected: mqtt={host}:{port} topic={PROCESS_TOPIC}")
    try:
        ProcessOrderBridge(supabase_client, mqtt_client).run_forever(interval)
    except KeyboardInterrupt:
        pass
    finally:
        mqtt_client.disconnect()
        mqtt_client.loop_stop()


if __name__ == "__main__":
    main()
