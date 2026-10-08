"""Supabase repository for collection sessions, raw data, and cycle results."""

import os
import json
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from supabase import Client, create_client


class RepositoryConfigurationError(RuntimeError):
    """Raised when the server-only Supabase credentials are unavailable."""


class RepositoryWriteError(RuntimeError):
    """Raised when Supabase rejects a persistence request."""


class SessionConflictError(RuntimeError):
    """Raised when an existing session has different collection semantics."""


def validate_packet_metrics(metrics):
    """Validate display-only JSON without permitting PCM or extra fields."""
    import math
    from system.ML.Condition.analysis import PREPROCESSING_VERSION

    if not isinstance(metrics, dict) or set(metrics) != {
        "preprocessing_version",
        "sph0645",
        "inmp441",
    }:
        raise ValueError("invalid packet metric fields")
    if metrics["preprocessing_version"] != PREPROCESSING_VERSION:
        raise ValueError("invalid packet preprocessing")
    for name, rate in (("sph0645", 4000), ("inmp441", 16000)):
        values = metrics[name]
        if not isinstance(values, dict) or set(values) != {
            "rms",
            "peak",
            "sample_count",
            "sample_rate",
        }:
            raise ValueError("invalid packet sensor fields")
        for field in ("rms", "peak"):
            value = values[field]
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value < 0
            ):
                raise ValueError("invalid packet magnitude")
        count = values["sample_count"]
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise ValueError("invalid packet sample count")
        if isinstance(values["sample_rate"], bool) or values["sample_rate"] != rate:
            raise ValueError("invalid packet sample rate")
        if values["peak"] < values["rms"]:
            raise ValueError("invalid packet peak")
    return json.loads(json.dumps(metrics, allow_nan=False))


def validate_runtime_metadata(runtime):
    """Pi-only metadata, never a Pico field or a training feature."""
    required = {
        "last_received_at",
        "stft_status",
        "operation_status",
        "ml_status",
        "stft_preview",
    }
    if not isinstance(runtime, dict) or set(runtime) not in (
        required,
        required | {"packet_metrics"},
    ):
        raise ValueError("invalid runtime fields")
    if "packet_metrics" in runtime:
        validate_packet_metrics(runtime["packet_metrics"])
    received = datetime.fromisoformat(runtime["last_received_at"])
    if received.tzinfo is None:
        raise ValueError("runtime receive time requires timezone")
    allowed = {
        "stft_status": {
            "WAITING_FOR_DATA",
            "BUFFERING",
            "RUNNING",
            "COMPLETED",
            "CONFIG_REQUIRED",
            "ANALYSIS_ERROR",
        },
        "operation_status": {
            "REFERENCE_REQUIRED",
            "THRESHOLD_REQUIRED",
            "WAITING",
            "NO_OPERATION",
            "OPERATION_DETECTED",
        },
        "ml_status": {
            "WAITING_FOR_OPERATION",
            "MODEL_REQUIRED",
            "READY",
            "INFERENCE_RUNNING",
            "COMPLETED",
            "ERROR",
        },
    }
    for name, values in allowed.items():
        if runtime[name] not in values:
            raise ValueError("invalid runtime status")
    preview = runtime["stft_preview"]
    if preview is not None:
        import math

        if not isinstance(preview, dict) or set(preview) != {"sph0645", "inmp441"}:
            raise ValueError("invalid preview sensors")
        for data in preview.values():
            if set(data) != {"relative_times", "frequencies", "magnitude"}:
                raise ValueError("invalid preview fields")
            times, frequencies, magnitude = (
                data[n] for n in ("relative_times", "frequencies", "magnitude")
            )
            if not times or not frequencies or len(magnitude) != len(frequencies):
                raise ValueError("invalid preview shape")
            if any(len(row) != len(times) for row in magnitude):
                raise ValueError("invalid preview shape")
            values = times + frequencies + [v for row in magnitude for v in row]
            if any(
                isinstance(v, bool)
                or not isinstance(v, (int, float))
                or not math.isfinite(v)
                or v < 0
                for v in values
            ):
                raise ValueError("invalid preview numbers")
            if any(
                b <= a for axis in (times, frequencies) for a, b in zip(axis, axis[1:])
            ):
                raise ValueError("invalid preview axes")
    # Reject NaN, unsupported objects and mutable aliases before persistence.
    return json.loads(json.dumps(runtime, allow_nan=False))


class CylinderResultRepository:
    """Persistence boundary for collection data and analysis results."""

    def __init__(self, client: Client | None = None) -> None:
        self._client = client
        # At most one confirmed session / last Raw write per fixed cylinder.
        self._confirmed_sessions = {}
        self._last_raw_rows = {}

    def ensure_collection_session(
        self, session: dict[str, Any], *, reject_existing: bool = False
    ) -> dict[str, Any]:
        """Create one immutable semantic record for a Pico session."""
        client = self._get_client()
        session_row = {
            "session_id": session["session_id"],
            "cylinder_id": session["cylinder_id"],
            "collection_mode": session["collection_mode"],
            "dataset_type": session["dataset_type"],
            "ground_truth": session.get("ground_truth"),
            "ground_truth_source": session.get("ground_truth_source"),
            "experiment_id": session.get("experiment_id"),
            "started_at": session["started_at"],
        }
        semantic_fields = (
            "cylinder_id",
            "collection_mode",
            "dataset_type",
            "ground_truth",
            "ground_truth_source",
            "experiment_id",
        )
        cached = self._confirmed_sessions.get(session_row["cylinder_id"])
        if (
            not reject_existing
            and cached
            and cached["session_id"] == session_row["session_id"]
        ):
            if any(
                cached.get(name) != session_row.get(name) for name in semantic_fields
            ):
                raise SessionConflictError("session collection semantics changed")
            return deepcopy(cached)

        try:
            if reject_existing:
                # Plain INSERT fails atomically if a previous run owns this session.
                client.table("collection_sessions").insert(session_row).execute()
            else:
                client.table("collection_sessions").upsert(
                    session_row,
                    on_conflict="session_id",
                    ignore_duplicates=True,
                ).execute()
            response = (
                client.table("collection_sessions")
                .select(
                    "session_id,cylinder_id,collection_mode,dataset_type,"
                    "ground_truth,ground_truth_source,experiment_id,started_at"
                )
                .eq("session_id", session["session_id"])
                .limit(1)
                .execute()
            )
        except Exception as error:
            raise RepositoryWriteError("Supabase session write failed") from error

        rows = response.data or []
        if not rows:
            raise RepositoryWriteError("Supabase session write was not confirmed")
        stored = rows[0]
        semantic_fields = (
            "cylinder_id",
            "collection_mode",
            "dataset_type",
            "ground_truth",
            "ground_truth_source",
            "experiment_id",
        )
        if any(stored.get(name) != session_row.get(name) for name in semantic_fields):
            raise SessionConflictError(
                "session_id is already registered with different collection semantics"
            )
        from system.MQTT.message_parser import ALLOWED_CYLINDER_IDS

        if session_row["cylinder_id"] in ALLOWED_CYLINDER_IDS:
            self._confirmed_sessions[session_row["cylinder_id"]] = deepcopy(stored)
        return stored

    def save_raw_data(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Upsert one parsed MQTT message by the approved QoS 1 identity."""
        client = self._get_client()
        updated_at = datetime.now(timezone.utc).isoformat()
        raw_row = {
            "cylinder_id": payload["cylinder_id"],
            "session_id": payload["session_id"],
            "sequence_id": payload["sequence_id"],
            "cycle_id": payload.get("cycle_id"),
            "measured_at": payload["timestamp"],
            "raw_payload": self._compact_raw_payload(payload),
            "updated_at": updated_at,
        }
        try:
            response = (
                client.table("raw_data")
                .upsert(
                    raw_row,
                    on_conflict="cylinder_id,session_id,sequence_id",
                )
                .execute()
            )
            from system.MQTT.message_parser import ALLOWED_CYLINDER_IDS

            cylinder = payload["cylinder_id"]
            self._last_raw_rows.pop(cylinder, None)
            if cylinder in ALLOWED_CYLINDER_IDS and isinstance(response.data, list):
                for row in response.data:
                    if (
                        isinstance(row, dict)
                        and row.get("id") is not None
                        and all(
                            row.get(name) == payload[name]
                            for name in ("cylinder_id", "session_id", "sequence_id")
                        )
                    ):
                        self._last_raw_rows[cylinder] = {
                            **{
                                name: payload[name]
                                for name in ("cylinder_id", "session_id", "sequence_id")
                            },
                            "id": row["id"],
                            "raw_payload": deepcopy(raw_row["raw_payload"]),
                        }
                        break
        except Exception as error:
            raise RepositoryWriteError("Supabase raw-data write failed") from error
        return {
            "cylinder_id": payload["cylinder_id"],
            "session_id": payload["session_id"],
            "sequence_id": payload["sequence_id"],
        }

    def save_processed_features_and_ml_result(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Upsert Cycle features first, then the related ML result."""
        client = self._get_client()
        updated_at = datetime.now(timezone.utc).isoformat()
        features = payload.get("features") or {}
        feature_row = {
            "cylinder_id": payload["cylinder_id"],
            "cycle_id": payload["cycle_id"],
            "session_id": payload["session_id"],
            "measured_at": payload["timestamp"],
            "sph0645_rms": features.get("sph0645_rms"),
            "inmp441_rms": features.get("inmp441_rms"),
            "sph0645_peak": features.get("sph0645_peak"),
            "inmp441_peak": features.get("inmp441_peak"),
            "sph0645_peak_to_peak": features.get("sph0645_peak_to_peak"),
            "inmp441_peak_to_peak": features.get("inmp441_peak_to_peak"),
            "sph0645_crest_factor": features.get("sph0645_crest_factor"),
            "inmp441_crest_factor": features.get("inmp441_crest_factor"),
            "fft_features": features.get("fft_features"),
            "updated_at": updated_at,
        }
        result_row = {
            "cylinder_id": payload["cylinder_id"],
            "cycle_id": payload["cycle_id"],
            "measured_at": payload["timestamp"],
            "prediction": payload["prediction"],
            "leakage_score": payload.get("leakage_score"),
            "updated_at": updated_at,
        }

        try:
            client.table("processed_features").upsert(
                feature_row,
                on_conflict="cylinder_id,cycle_id",
            ).execute()
            client.table("ml_results").upsert(
                result_row,
                on_conflict="cylinder_id,cycle_id",
            ).execute()
        except Exception as error:
            raise RepositoryWriteError("Supabase write failed") from error

        return {
            "cylinder_id": payload["cylinder_id"],
            "cycle_id": payload["cycle_id"],
            "session_id": payload["session_id"],
        }

    def save_runtime_metadata(self, identity, runtime, preview_keep_rows=None):
        """Update only Pi metadata on an already stored Raw row.

        Single Pi writer per cylinder is required. No Sensor fields, cycle_id,
        measured_at or creation time are changed. Failed writes are explicit.
        Preview pruning precedes insertion so failures cannot grow retention.
        """
        metadata = validate_runtime_metadata(runtime)
        client = self._get_client()
        try:
            cached = self._last_raw_rows.get(identity["cylinder_id"])
            if cached and all(
                cached[name] == identity[name]
                for name in ("cylinder_id", "session_id", "sequence_id")
            ):
                rows = [cached]
            else:
                query = client.table("raw_data").select("id,raw_payload")
                for name in ("cylinder_id", "session_id", "sequence_id"):
                    query = query.eq(name, identity[name])
                rows = query.limit(1).execute().data or []
            if not rows:
                raise ValueError("Raw row missing")
            if metadata["stft_preview"] is not None:
                if (
                    isinstance(preview_keep_rows, bool)
                    or not isinstance(preview_keep_rows, int)
                    or preview_keep_rows < 1
                ):
                    raise ValueError("CONFIG_REQUIRED: preview_keep_rows")
                self._prune_previews(
                    identity["cylinder_id"], preview_keep_rows, rows[0]["id"]
                )
            raw = deepcopy(rows[0]["raw_payload"])
            raw["runtime"] = metadata
            result = (
                client.table("raw_data")
                .update({"raw_payload": raw})
                .eq("id", rows[0]["id"])
                .select("id")
                .execute()
            )
            if not result.data:
                raise ValueError("Runtime update not confirmed")
        except Exception as error:
            raise RepositoryWriteError("Supabase runtime write failed") from error

    def _prune_previews(self, cylinder, keep_rows, current_id):
        client = self._get_client()
        query = (
            client.table("raw_data")
            .select("id,raw_payload")
            .eq("cylinder_id", cylinder)
            .neq("id", current_id)
            .not_.is_("raw_payload->runtime->>stft_preview", "null")
            .order("id", desc=True)
        )
        # Bounded maintenance: at most keep_rows removals per save. If an
        # older backlog remains, refuse the new preview and retry next packet.
        old = query.range(keep_rows - 1, 2 * keep_rows - 2).execute().data or []
        for row in old:
            raw = deepcopy(row["raw_payload"])
            raw["runtime"]["stft_preview"] = None
            result = (
                client.table("raw_data")
                .update({"raw_payload": raw})
                .eq("id", row["id"])
                .select("id")
                .execute()
            )
            if not result.data:
                raise ValueError("Preview pruning not confirmed")
        # An unfilled ordered range proves there are no older matching rows.
        # Full pages may hide a backlog, so retain the verification below.
        if len(old) < keep_rows:
            return
        remaining = (
            client.table("raw_data")
            .select("id")
            .eq("cylinder_id", cylinder)
            .neq("id", current_id)
            .not_.is_("raw_payload->runtime->>stft_preview", "null")
            .order("id", desc=True)
            .range(keep_rows - 1, keep_rows - 1)
            .execute()
            .data
        )
        if remaining:
            raise ValueError("Preview retention backlog")

    @staticmethod
    def _monitoring_projection():
        """History carries scalar statuses/metrics, never repeated matrices."""
        return (
            "cylinder_id,session_id,sequence_id,measured_at,"
            "last_received_at:raw_payload->runtime->>last_received_at,"
            "stft_status:raw_payload->runtime->>stft_status,"
            "operation_status:raw_payload->runtime->>operation_status,"
            "ml_status:raw_payload->runtime->>ml_status,"
            "packet_metrics:raw_payload->runtime->packet_metrics"
        )

    @staticmethod
    def _monitoring_row(row):
        row = dict(row)
        if "runtime" not in row:
            row["runtime"] = {
                name: row.pop(name)
                for name in (
                    "last_received_at",
                    "stft_status",
                    "operation_status",
                    "ml_status",
                    "packet_metrics",
                )
                if row.get(name) is not None
            }
        return row

    def read_monitoring(self, cylinder, limit):
        """Server-only OPERATION projection: never return PCM or Ground Truth."""
        from system.MQTT.message_parser import ALLOWED_CYLINDER_IDS

        if cylinder not in ALLOWED_CYLINDER_IDS or not 1 <= limit <= 300:
            raise ValueError("invalid monitoring selection")
        client = self._get_client()
        try:
            rows = (
                client.table("raw_data")
                .select(
                    self._monitoring_projection()
                    + ",collection_sessions!inner(collection_mode)"
                )
                .eq("cylinder_id", cylinder)
                .eq("collection_sessions.collection_mode", "OPERATION")
                .order("id", desc=True)
                .limit(limit)
                .execute()
                .data
                or []
            )
            if not rows:
                return {
                    "rows": [],
                    "features": None,
                    "prediction": None,
                    "preview": None,
                }
            rows = [self._monitoring_row(row) for row in rows]
            session = rows[0]["session_id"]
            # Raw INSERT and runtime PATCH are separate requests. Do not let an
            # in-flight row hide the last processed row, even for limit=1.
            if not (rows[0].get("runtime") or {}).get("last_received_at"):
                processed = [
                    row
                    for row in rows[1:]
                    if row["session_id"] == session
                    and (row.get("runtime") or {}).get("last_received_at")
                ]
                if not processed:
                    processed = (
                        client.table("raw_data")
                        .select(self._monitoring_projection())
                        .eq("cylinder_id", cylinder)
                        .eq("session_id", session)
                        .lte("sequence_id", rows[0]["sequence_id"])
                        .not_.is_("raw_payload->runtime->>last_received_at", "null")
                        .order("sequence_id", desc=True)
                        .limit(1)
                        .execute()
                        .data
                        or []
                    )
                if processed:
                    head = self._monitoring_row(processed[0])
                    rows = [head] + [
                        row
                        for row in rows[1:]
                        if (row["session_id"], row["sequence_id"])
                        != (head["session_id"], head["sequence_id"])
                    ]
            features = (
                client.table("processed_features")
                .select(
                    "cycle_id,session_id,measured_at,sph0645_rms,inmp441_rms,fft_features"
                )
                .eq("cylinder_id", cylinder)
                .eq("session_id", session)
                .order("measured_at", desc=True)
                .limit(1)
                .execute()
                .data
                or []
            )
            prediction = []
            if features:
                prediction = (
                    client.table("ml_results")
                    .select(
                        "cycle_id,measured_at,prediction,leakage_score,model_name,model_version"
                    )
                    .eq("cylinder_id", cylinder)
                    .eq("cycle_id", features[0]["cycle_id"])
                    .limit(1)
                    .execute()
                    .data
                    or []
                )
            preview = (
                client.table("raw_data")
                .select("sequence_id,measured_at,runtime:raw_payload->runtime")
                .eq("cylinder_id", cylinder)
                .eq("session_id", session)
                .lte("sequence_id", rows[0]["sequence_id"])
                .not_.is_("raw_payload->runtime->>stft_preview", "null")
                .order("sequence_id", desc=True)
                .limit(1)
                .execute()
                .data
                or []
            )
            return {
                "rows": list(reversed(rows)),
                "features": features[0] if features else None,
                "prediction": prediction[0] if prediction else None,
                "preview": preview[0] if preview else None,
            }
        except Exception as error:
            raise RepositoryWriteError("Supabase monitoring read failed") from error

    def load_training_dataset(self) -> list[dict[str, Any]]:
        """Load only explicitly labelled TRAINING feature rows."""
        client = self._get_client()
        try:
            session_response = (
                client.table("collection_sessions")
                .select("session_id,dataset_type,ground_truth")
                .eq("collection_mode", "TRAINING")
                .in_(
                    "dataset_type",
                    ("TRAINING_NORMAL", "TRAINING_ABNORMAL"),
                )
                .execute()
            )
            sessions = {
                row["session_id"]: row
                for row in (session_response.data or [])
                if self._is_valid_training_session(row)
            }
            if not sessions:
                return []
            feature_response = (
                client.table("processed_features")
                .select("*")
                .in_("session_id", tuple(sessions))
                .execute()
            )
        except Exception as error:
            raise RepositoryWriteError("Supabase training-data read failed") from error

        dataset = []
        for feature_row in feature_response.data or []:
            session = sessions.get(feature_row.get("session_id"))
            if session is None:
                continue
            row = dict(feature_row)
            row["dataset_type"] = session["dataset_type"]
            row["ground_truth"] = session["ground_truth"]
            dataset.append(row)
        return dataset

    @staticmethod
    def _compact_raw_payload(payload: dict[str, Any]) -> dict[str, Any]:
        raw_payload = {
            name: value
            for name, value in payload.items()
            if name not in {"duplicate_key", "cycle_id", "runtime"}
        }
        for sensor_name in ("sph0645", "inmp441"):
            chunk = raw_payload.get(sensor_name)
            if isinstance(chunk, dict):
                raw_payload[sensor_name] = {
                    name: value for name, value in chunk.items() if name != "samples"
                }
        return raw_payload

    @staticmethod
    def _is_valid_training_session(row: dict[str, Any]) -> bool:
        return (
            row.get("dataset_type") == "TRAINING_NORMAL"
            and row.get("ground_truth") == "NORMAL"
        ) or (
            row.get("dataset_type") == "TRAINING_ABNORMAL"
            and row.get("ground_truth") == "SEAL_LEAK"
        )

    def _get_client(self) -> Client:
        if self._client is not None:
            return self._client

        supabase_url = os.environ.get("SUPABASE_URL")
        service_role_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if not supabase_url or not service_role_key:
            raise RepositoryConfigurationError(
                "Supabase server credentials are not configured"
            )

        self._client = create_client(supabase_url, service_role_key)
        return self._client
