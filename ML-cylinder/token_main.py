"""Production entry point for ordered Pico acquisition and existing analysis."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
from pathlib import Path

import paho.mqtt.client as mqtt

from config import Settings
from src.database import Database
from src.inference_excel_store import AsyncInferenceExcelStore
from src.logger_config import configure_logging
from src.ml_predictor import MLPredictor
from src.pipeline import SensorPipeline
from src.supabase_uploader import SupabaseUploader
from src.three_model_inference import MODEL_PATHS, RULPredictor
from src.token_ingestor import RawPacketWriter, StartupCommunicationGate, TokenManager

LOGGER = logging.getLogger("acoustic")


async def main() -> None:
    settings = Settings.load()
    settings.create_directories()
    configure_logging(settings.log_path, False)
    # Analysis storage and models are deliberately delayed until every Pico
    # has answered the startup communication check.
    analysis_db: Database | None = None
    uploader: SupabaseUploader | None = None
    excel: AsyncInferenceExcelStore | None = None
    pipeline: SensorPipeline | None = None
    loop = asyncio.get_running_loop()
    analysis_queue: asyncio.Queue[dict | None] = asyncio.Queue(
        int(os.getenv("ANALYSIS_QUEUE_SIZE", "256")))
    writer = RawPacketWriter(settings.ingest_database_path,
                             int(os.getenv("ANALYSIS_QUEUE_SIZE", "256")))
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id=os.getenv("MQTT_CLIENT_ID", "pi5-acoustic-ingestor"),
                         clean_session=False)
    if settings.mqtt_username:
        client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
    client.reconnect_delay_set(1, 60)

    async def publish(topic: str, body: str, qos: int) -> None:
        info = client.publish(topic, body, qos=qos, retain=False)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"MQTT publish failed rc={info.rc}")

    manager = TokenManager(
        writer, publish, analysis_queue,
        float(os.getenv("TOKEN_TIMEOUT_SECONDS", "30")),
        float(os.getenv("TOKEN_CYCLE_INTERVAL_SECONDS", "60")),
    )
    gate = StartupCommunicationGate(
        publish,
        timeout_seconds=float(os.getenv("PICO_STARTUP_CHECK_TIMEOUT_SECONDS", "30")),
    )
    connected = asyncio.Event()
    stopped = asyncio.Event()
    acquisition_started = asyncio.Event()

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            client.subscribe(os.getenv("MQTT_TOPIC", "smartCylinder/+/+/raw"), qos=1)
            LOGGER.info("MQTT connected; raw topic subscribed")
            loop.call_soon_threadsafe(connected.set)
        else:
            LOGGER.error("MQTT connection failed: %s", reason_code)

    def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
        loop.call_soon_threadsafe(connected.clear)
        LOGGER.warning("MQTT disconnected during service: %s", reason_code)

    def on_message(client, userdata, message):
        # Before the gate opens this is a communication proof only.  It is
        # intentionally not written to SQLite and cannot reach ML/upload.
        handler = manager.handle if acquisition_started.is_set() else gate.observe
        asyncio.run_coroutine_threadsafe(handler(message.topic, bytes(message.payload)), loop)

    client.on_connect, client.on_message, client.on_disconnect = on_connect, on_message, on_disconnect
    client.connect_async(settings.mqtt_host, settings.mqtt_port, settings.mqtt_keepalive)
    client.loop_start()

    async def analyze() -> None:
        while True:
            payload = await analysis_queue.get()
            try:
                if payload is None:
                    return
                assert pipeline is not None
                await asyncio.to_thread(pipeline.process, payload)
            except Exception:
                LOGGER.exception("analysis failed device=%s sequence=%s",
                                 payload.get("device_id"), payload.get("sequence"))
            finally:
                analysis_queue.task_done()

    async def upload() -> None:
        interval = float(os.getenv("UPLOAD_INTERVAL_SECONDS", "10"))
        batch = min(200, max(50, int(os.getenv("UPLOAD_BATCH_SIZE", "100"))))
        while manager.running:
            assert uploader is not None
            await asyncio.to_thread(uploader.retry_pending, batch)
            await asyncio.sleep(interval)

    for name in ("SIGINT", "SIGTERM"):
        if hasattr(signal, name):
            loop.add_signal_handler(getattr(signal, name), stopped.set)
    try:
        while not connected.is_set() and not stopped.is_set():
            try:
                await asyncio.wait_for(connected.wait(), timeout=0.5)
            except asyncio.TimeoutError:
                pass
        if stopped.is_set():
            return
        # Clear leftovers from an earlier, incomplete startup.  Raw messages
        # received while checking are discarded by on_message above.
        RawPacketWriter.discard_unverified(settings.ingest_database_path)
        retry_seconds = float(os.getenv("PICO_STARTUP_CHECK_RETRY_SECONDS", "10"))
        while not stopped.is_set() and not await gate.check_once():
            LOGGER.warning("acquisition remains locked; waiting for every Pico")
            try:
                await asyncio.wait_for(stopped.wait(), retry_seconds)
            except asyncio.TimeoutError:
                pass
        if stopped.is_set():
            return
        acquisition_started.set()
        LOGGER.info("all Pico communication checks passed; acquisition unlocked")
        analysis_db = Database(settings.database_path)
        uploader = SupabaseUploader(analysis_db, settings.supabase_url,
                                    settings.supabase_key, "measurements")
        excel = AsyncInferenceExcelStore(settings.inference_excel_path)
        pipeline = SensorPipeline(
            analysis_db,
            {"sph0645": MLPredictor(MODEL_PATHS["acoustic_vibration"]),
             "inmp441": MLPredictor(MODEL_PATHS["sound"])},
            uploader, settings.use_hann_window, None, excel,
            RULPredictor(MODEL_PATHS["rul"]),
        )
        writer_task = asyncio.create_task(writer.run())
        workers = [asyncio.create_task(analyze()) for _ in range(
            int(os.getenv("ANALYSIS_WORKERS", "2")))]
        upload_task = asyncio.create_task(upload())
        token_task = asyncio.create_task(manager.run())
        await stopped.wait()
    finally:
        # Stop reception first, drain analysis, commit writer, then close resources.
        manager.stop()
        token_task = locals().get("token_task")
        upload_task = locals().get("upload_task")
        writer_task = locals().get("writer_task")
        workers = locals().get("workers", [])
        if token_task:
            token_task.cancel()
        if upload_task:
            upload_task.cancel()
        client.disconnect()
        client.loop_stop()
        if writer_task:
            await writer.close()
            await writer_task
            await analysis_queue.join()
            for _ in workers:
                await analysis_queue.put(None)
            await asyncio.gather(*workers, return_exceptions=True)
        await asyncio.gather(*(task for task in (token_task, upload_task) if task), return_exceptions=True)
        if excel is not None:
            excel.close()
        if analysis_db is not None:
            analysis_db.close()


if __name__ == "__main__":
    asyncio.run(main())
