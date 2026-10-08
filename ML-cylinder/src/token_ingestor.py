"""Durable, ordered Pico MQTT ingestion for the Raspberry Pi 5 service."""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable

LOGGER = logging.getLogger(__name__)
DEVICES = tuple(f"pico{i:02d}" for i in range(1, 7))
REQUIRED_FIELDS = {
    "device_id", "boot_id", "sequence", "timestamp", "timestamp_quality",
    "cylinder_state", "sensor_type", "sample_rate", "samples",
    "firmware_version", "frame_duration_ms", "dropped_frames",
}


@dataclass(slots=True)
class StoreRequest:
    payload: dict
    raw_payload: bytes
    result: asyncio.Future[bool]


@dataclass(slots=True)
class TimeoutRequest:
    device_id: str
    cycle_id: int
    seconds: float
    result: asyncio.Future[None]


class RawPacketWriter:
    """The only task allowed to write raw packets; completion means COMMIT succeeded."""

    def __init__(self, path: Path, queue_size: int = 256):
        self.path = path
        self.queue: asyncio.Queue[StoreRequest | TimeoutRequest | None] = asyncio.Queue(queue_size)
        self.connection: sqlite3.Connection | None = None

    async def run(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        connection.executescript("""
        CREATE TABLE IF NOT EXISTS raw_packets(
          id INTEGER PRIMARY KEY, device_id TEXT NOT NULL, boot_id TEXT NOT NULL,
          sensor_type TEXT NOT NULL, sequence INTEGER NOT NULL, cycle_id INTEGER,
          payload BLOB NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
          received_at REAL NOT NULL, UNIQUE(device_id,boot_id,sensor_type,sequence)
        );
        CREATE INDEX IF NOT EXISTS idx_raw_pending ON raw_packets(status,id);
        CREATE TABLE IF NOT EXISTS token_timeouts(
          id INTEGER PRIMARY KEY, device_id TEXT NOT NULL, cycle_id INTEGER NOT NULL,
          timeout_seconds REAL NOT NULL, occurred_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS upload_queue(
          id INTEGER PRIMARY KEY, measurement_id TEXT NOT NULL UNIQUE,
          payload TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
          attempt INTEGER NOT NULL DEFAULT 0, next_attempt_at REAL NOT NULL DEFAULT 0,
          last_error TEXT
        );
        UPDATE raw_packets SET status='pending' WHERE status='processing';
        UPDATE upload_queue SET status='retry' WHERE status='sending';
        """)
        connection.commit()
        self.connection = connection
        try:
            while True:
                request = await self.queue.get()
                if request is None:
                    self.queue.task_done()
                    break
                try:
                    if isinstance(request, TimeoutRequest):
                        connection.execute(
                            "INSERT INTO token_timeouts(device_id,cycle_id,timeout_seconds,occurred_at) VALUES(?,?,?,?)",
                            (request.device_id, request.cycle_id, request.seconds, time.time()),
                        )
                        connection.commit()
                        request.result.set_result(None)
                        continue
                    p = request.payload
                    cursor = connection.execute(
                        """INSERT OR IGNORE INTO raw_packets
                        (device_id,boot_id,sensor_type,sequence,cycle_id,payload,received_at)
                        VALUES(?,?,?,?,?,?,?)""",
                        (p["device_id"], p["boot_id"], p["sensor_type"], p["sequence"],
                         p.get("cycle_id"), request.raw_payload, time.time()),
                    )
                    connection.commit()
                    request.result.set_result(cursor.rowcount == 1)
                except Exception as exc:
                    connection.rollback()
                    request.result.set_exception(exc)
                finally:
                    self.queue.task_done()
        finally:
            connection.commit()
            connection.close()
            self.connection = None

    async def store(self, payload: dict, raw_payload: bytes) -> bool:
        future = asyncio.get_running_loop().create_future()
        await self.queue.put(StoreRequest(payload, raw_payload, future))
        return await future

    async def timeout(self, device_id: str, cycle_id: int, seconds: float) -> None:
        future = asyncio.get_running_loop().create_future()
        await self.queue.put(TimeoutRequest(device_id, cycle_id, seconds, future))
        await future

    async def close(self) -> None:
        await self.queue.put(None)
        await self.queue.join()

    @staticmethod
    def discard_unverified(path: Path) -> None:
        """Remove packets left from a run that never passed the Pico check.

        This is deliberately limited to the acquisition database.  Confirmed
        analysis history is kept; unverified packets must never reach it.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path, timeout=5)
        try:
            connection.execute("PRAGMA busy_timeout=5000")
            for table in ("raw_packets", "token_timeouts", "upload_queue"):
                if connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
                ).fetchone():
                    connection.execute(f"DELETE FROM {table}")
            connection.commit()
        finally:
            connection.close()


Publish = Callable[[str, str, int], Awaitable[None]]


class StartupCommunicationGate:
    """Require one valid token response from every Pico before acquisition.

    Packets received during this check are only proof of communication: they
    are never persisted or passed to the analysis queue.
    """

    def __init__(self, publish: Publish, devices: tuple[str, ...] = DEVICES,
                 timeout_seconds: float = 30):
        self.publish = publish
        self.devices = devices
        self.timeout_seconds = timeout_seconds
        self._cycle_id = 0
        self._expected_device: str | None = None
        self._waiter: asyncio.Future[None] | None = None

    async def check_once(self) -> bool:
        self._cycle_id = int(time.time() * 1000)
        for device in self.devices:
            self._expected_device = device
            self._waiter = asyncio.get_running_loop().create_future()
            token = {
                "cycle_id": self._cycle_id,
                "device_id": device,
                "timeout_seconds": self.timeout_seconds,
                "purpose": "startup_communication_check",
            }
            try:
                await self.publish(
                    f"smartCylinder/control/{device}/token", json.dumps(token), 1
                )
                await asyncio.wait_for(self._waiter, self.timeout_seconds)
            except (asyncio.TimeoutError, Exception) as exc:
                LOGGER.warning("startup communication check failed: device=%s error=%s", device, exc)
                self._expected_device = None
                self._waiter = None
                return False
        self._expected_device = None
        self._waiter = None
        return True

    async def observe(self, topic: str, raw_payload: bytes) -> None:
        """Accept only the response to the currently-issued check token."""
        try:
            payload = json.loads(raw_payload)
            TokenManager.validate(topic, payload)
        except Exception:
            LOGGER.warning("invalid packet discarded during startup communication check: %s", topic)
            return
        if (
            payload.get("device_id") == self._expected_device
            and payload.get("cycle_id") == self._cycle_id
            and self._waiter is not None
            and not self._waiter.done()
        ):
            self._waiter.set_result(None)


class TokenManager:
    def __init__(self, writer: RawPacketWriter, publish: Publish, analysis_queue: asyncio.Queue[dict],
                 timeout_seconds: float = 30, cycle_interval_seconds: float = 60):
        self.writer, self.publish, self.analysis_queue = writer, publish, analysis_queue
        self.timeout_seconds, self.cycle_interval_seconds = timeout_seconds, cycle_interval_seconds
        self.cycle_id = int(time.time())
        self.index = 0
        self.waiter: asyncio.Future[None] | None = None
        self.running = True

    @staticmethod
    def validate(topic: str, payload: dict) -> None:
        missing = REQUIRED_FIELDS - payload.keys()
        if missing:
            raise ValueError("missing fields: " + ", ".join(sorted(missing)))
        parts = topic.split("/")
        if len(parts) != 4 or parts[0] != "smartCylinder" or parts[2] != "inmp441" or parts[3] != "raw":
            raise ValueError("invalid raw topic")
        if payload["device_id"] != parts[1] or payload["device_id"] not in DEVICES:
            raise ValueError("topic/device_id mismatch")
        if not isinstance(payload["boot_id"], str) or not payload["boot_id"]:
            raise ValueError("invalid boot_id")
        if isinstance(payload["sequence"], bool) or not isinstance(payload["sequence"], int) or payload["sequence"] < 0:
            raise ValueError("invalid sequence")
        if "cycle_id" in payload and (isinstance(payload["cycle_id"], bool) or not isinstance(payload["cycle_id"], int)):
            raise ValueError("invalid cycle_id")
        if not isinstance(payload["samples"], list):
            raise ValueError("invalid samples")

    async def handle(self, topic: str, raw_payload: bytes) -> None:
        try:
            payload = json.loads(raw_payload)
            self.validate(topic, payload)
            inserted = await self.writer.store(payload, raw_payload)
        except Exception:
            LOGGER.exception("raw packet rejected topic=%s", topic)
            return
        number = int(payload["device_id"][-2:])
        LOGGER.info("pico %s : raw packet committed sequence=%s", number, payload["sequence"])
        ack = {key: payload[key] for key in ("device_id", "boot_id", "sequence")}
        ack.update({"cycle_id": payload.get("cycle_id"), "status": "stored"})
        await self.publish(f"smartCylinder/control/{payload['device_id']}/ack", json.dumps(ack), 1)
        LOGGER.info("pico %s : SQLite committed; stored ACK sent", number)
        if inserted:
            await self.analysis_queue.put(payload)
        expected = DEVICES[self.index]
        if payload["device_id"] == expected and payload.get("cycle_id") == self.cycle_id:
            if self.waiter and not self.waiter.done():
                self.waiter.set_result(None)

    async def run(self) -> None:
        while self.running:
            device = DEVICES[self.index]
            number = self.index + 1
            token = {"cycle_id": self.cycle_id, "device_id": device,
                     "timeout_seconds": self.timeout_seconds}
            self.waiter = asyncio.get_running_loop().create_future()
            await self.publish(f"smartCylinder/control/{device}/token", json.dumps(token), 1)
            LOGGER.info("pico %s : transmit token sent cycle_id=%s", number, self.cycle_id)
            try:
                await asyncio.wait_for(self.waiter, self.timeout_seconds)
            except asyncio.TimeoutError:
                await self.writer.timeout(device, self.cycle_id, self.timeout_seconds)
                LOGGER.warning("pico %s : response timeout cycle_id=%s timeout_seconds=%s",
                               number, self.cycle_id, self.timeout_seconds)
            self.index += 1
            if self.index == len(DEVICES):
                self.index = 0
                self.cycle_id += 1
                try:
                    await asyncio.sleep(self.cycle_interval_seconds)
                except asyncio.CancelledError:
                    break

    def stop(self) -> None:
        self.running = False
        if self.waiter and not self.waiter.done():
            self.waiter.cancel()
