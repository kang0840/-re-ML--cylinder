import asyncio
import json
import sqlite3

from src.token_ingestor import RawPacketWriter, StartupCommunicationGate, TokenManager


def packet(device="pico01", cycle=1, sequence=100):
    return {"device_id": device, "boot_id": "boot-a", "sequence": sequence,
            "timestamp": 1785830000, "timestamp_quality": "synchronized",
            "cylinder_state": "active", "sensor_type": "inmp441", "sample_rate": 16000,
            "cycle_id": cycle, "samples": [0, 1], "firmware_version": "1.0.0",
            "frame_duration_ms": 32, "dropped_frames": 0}


def test_commit_ack_duplicate_and_pragmas(tmp_path):
    async def scenario():
        published = []
        async def publish(topic, body, qos): published.append((topic, json.loads(body), qos))
        writer = RawPacketWriter(tmp_path / "a.db")
        task = asyncio.create_task(writer.run())
        manager = TokenManager(writer, publish, asyncio.Queue())
        body = json.dumps(packet(cycle=manager.cycle_id)).encode()
        await manager.handle("smartCylinder/pico01/inmp441/raw", body)
        await manager.handle("smartCylinder/pico01/inmp441/raw", body)
        await writer.close(); await task
        assert len(published) == 2
        assert all(item[1]["status"] == "stored" and item[2] == 1 for item in published)
        with sqlite3.connect(tmp_path / "a.db") as db:
            assert db.execute("select count(*) from raw_packets").fetchone()[0] == 1
            assert db.execute("pragma journal_mode").fetchone()[0] == "wal"
            assert db.execute("pragma synchronous").fetchone()[0] == 2
            assert db.execute("pragma busy_timeout").fetchone()[0] == 5000
    asyncio.run(scenario())


def test_timeout_advances_to_next_device(tmp_path):
    async def scenario():
        published = []
        async def publish(topic, body, qos): published.append(topic)
        writer = RawPacketWriter(tmp_path / "b.db")
        writer_task = asyncio.create_task(writer.run())
        manager = TokenManager(writer, publish, asyncio.Queue(), .02, 99)
        manager_task = asyncio.create_task(manager.run())
        while len(published) < 2: await asyncio.sleep(.005)
        manager.stop(); manager_task.cancel()
        try: await manager_task
        except asyncio.CancelledError: pass
        await writer.close(); await writer_task
        assert published[:2] == ["smartCylinder/control/pico01/token", "smartCylinder/control/pico02/token"]
        with sqlite3.connect(tmp_path / "b.db") as db:
            assert db.execute("select device_id from token_timeouts order by id limit 1").fetchone()[0] == "pico01"
    asyncio.run(scenario())


def test_restart_recovers_transient_states(tmp_path):
    path = tmp_path / "c.db"
    async def first():
        writer = RawPacketWriter(path); task = asyncio.create_task(writer.run())
        await writer.store(packet(), json.dumps(packet()).encode())
        assert writer.connection
        writer.connection.execute("update raw_packets set status='processing'")
        writer.connection.execute("insert into upload_queue(measurement_id,payload,status) values('m','{}','sending')")
        writer.connection.commit(); await writer.close(); await task
    async def second():
        writer = RawPacketWriter(path); task = asyncio.create_task(writer.run())
        while writer.connection is None: await asyncio.sleep(0)
        assert writer.connection.execute("select status from raw_packets").fetchone()[0] == "pending"
        assert writer.connection.execute("select status from upload_queue").fetchone()[0] == "retry"
        await writer.close(); await task
    asyncio.run(first()); asyncio.run(second())


def test_startup_gate_requires_all_picos_and_discards_check_packets():
    async def scenario():
        published = []

        async def publish(topic, body, qos):
            published.append((topic, json.loads(body), qos))

        gate = StartupCommunicationGate(publish, devices=("pico01", "pico02"), timeout_seconds=.2)
        task = asyncio.create_task(gate.check_once())
        while len(published) < 1:
            await asyncio.sleep(0)
        await gate.observe(
            "smartCylinder/pico01/inmp441/raw",
            json.dumps(packet("pico01", published[0][1]["cycle_id"])).encode(),
        )
        while len(published) < 2:
            await asyncio.sleep(0)
        await gate.observe(
            "smartCylinder/pico02/inmp441/raw",
            json.dumps(packet("pico02", published[1][1]["cycle_id"])).encode(),
        )
        assert await task is True
    asyncio.run(scenario())


def test_discard_unverified_packets(tmp_path):
    async def scenario():
        path = tmp_path / "unverified.db"
        writer = RawPacketWriter(path)
        task = asyncio.create_task(writer.run())
        payload = packet()
        await writer.store(payload, json.dumps(payload).encode())
        await writer.close()
        await task
        RawPacketWriter.discard_unverified(path)
        with sqlite3.connect(path) as db:
            assert db.execute("select count(*) from raw_packets").fetchone()[0] == 0
    asyncio.run(scenario())
