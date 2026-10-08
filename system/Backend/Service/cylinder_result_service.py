"""Application service for sensor collection and completed analysis cycles."""

import os

from typing import Any

from system.DB.Supabase.cylinder_result_repository import (
    CylinderResultRepository,
    RepositoryConfigurationError,
    RepositoryWriteError,
    SessionConflictError,
)

COLLECTION_MODES = ("TRAINING", "OPERATION", "TEST")


class ResultStorageUnavailableError(RuntimeError):
    """Raised when server-only Supabase credentials are unavailable."""


class CollectionModeError(RuntimeError):
    """Raised when collection mode cannot safely classify a message."""


def resolve_collection_route(
    collection_mode: str,
    cylinder_id: str,
    training_ground_truth: str | None = None,
    training_cylinder_id: str | None = None,
) -> dict[str, Any]:
    """Resolve dataset meaning from both collection mode and cylinder identity."""
    if collection_mode not in COLLECTION_MODES:
        raise CollectionModeError(
            "COLLECTION_MODE must be TRAINING, OPERATION, or TEST"
        )
    if collection_mode == "TRAINING":
        if training_ground_truth is not None or training_cylinder_id is not None:
            if training_ground_truth not in ("NORMAL", "SEAL_LEAK"):
                raise CollectionModeError("CONFIG_REQUIRED: training ground truth")
            if training_cylinder_id not in tuple(
                "cylinder_%02d" % number for number in range(1, 7)
            ):
                raise CollectionModeError("CONFIG_REQUIRED: training cylinder")
            if cylinder_id != training_cylinder_id:
                raise CollectionModeError("UNSELECTED_TRAINING_DEVICE")
            return {
                "collection_mode": "TRAINING",
                "dataset_type": (
                    "TRAINING_NORMAL"
                    if training_ground_truth == "NORMAL"
                    else "TRAINING_ABNORMAL"
                ),
                "ground_truth": training_ground_truth,
                "ground_truth_source": "MANUAL_EXPERIMENT",
            }
        if cylinder_id == "cylinder_01":
            return {
                "collection_mode": "TRAINING",
                "dataset_type": "TRAINING_NORMAL",
                "ground_truth": "NORMAL",
                "ground_truth_source": "MANUAL_EXPERIMENT",
            }
        if cylinder_id == "cylinder_02":
            return {
                "collection_mode": "TRAINING",
                "dataset_type": "TRAINING_ABNORMAL",
                "ground_truth": "SEAL_LEAK",
                "ground_truth_source": "MANUAL_EXPERIMENT",
            }
        raise CollectionModeError(
            "TRAINING mode accepts only cylinder_01 and cylinder_02"
        )
    if collection_mode == "TEST":
        return {
            "collection_mode": "TEST",
            "dataset_type": "TEST",
            "ground_truth": None,
            "ground_truth_source": None,
        }
    return {
        "collection_mode": "OPERATION",
        "dataset_type": "RAW_OPERATION",
        "ground_truth": None,
        "ground_truth_source": None,
    }


class CylinderResultService:
    """Coordinate result persistence without owning HTTP or database details."""

    def __init__(
        self,
        repository: CylinderResultRepository | None = None,
        *,
        training_ground_truth: str | None = None,
        training_cylinder_id: str | None = None,
        experiment_id: str | None = None,
    ) -> None:
        self._repository = repository or CylinderResultRepository()
        self.training_ground_truth = training_ground_truth
        self.training_cylinder_id = training_cylinder_id
        self.experiment_id = experiment_id
        self._training_session_id = None
        if training_ground_truth is not None or training_cylinder_id is not None:
            self.resolve_route("TRAINING", training_cylinder_id)
            if not isinstance(experiment_id, str) or not experiment_id.strip():
                raise CollectionModeError("CONFIG_REQUIRED: experiment ID")

    def resolve_route(self, collection_mode, cylinder_id):
        return resolve_collection_route(
            collection_mode,
            cylinder_id,
            self.training_ground_truth,
            self.training_cylinder_id,
        )

    def record_sensor_message(
        self,
        payload: dict[str, Any],
        is_duplicate: bool = False,
        collection_mode: str | None = None,
        experiment_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Store one Parser-approved MQTT message under an explicit collection mode."""
        if is_duplicate:
            return None
        selected_mode = collection_mode or os.environ.get("COLLECTION_MODE")
        if selected_mode is None:
            raise CollectionModeError("COLLECTION_MODE is required")
        route = self.resolve_route(selected_mode, payload["cylinder_id"])
        explicit_training = (
            selected_mode == "TRAINING" and self.training_ground_truth is not None
        )
        new_session = explicit_training and self._training_session_id is None
        if new_session and payload["sequence_id"] != 1:
            raise CollectionModeError("NEW_SESSION_REQUIRED: reboot Pico after start")
        if explicit_training and self._training_session_id not in (
            None,
            payload["session_id"],
        ):
            raise CollectionModeError("NEW_RUN_REQUIRED: restart collection launcher")
        session = {
            "session_id": payload["session_id"],
            "cylinder_id": payload["cylinder_id"],
            "started_at": payload["timestamp"],
            "experiment_id": self.experiment_id if explicit_training else experiment_id,
            **route,
        }
        try:
            if new_session:
                self._repository.ensure_collection_session(
                    session, reject_existing=True
                )
                self._training_session_id = payload["session_id"]
            else:
                self._repository.ensure_collection_session(session)
            return self._repository.save_raw_data(payload)
        except RepositoryConfigurationError as error:
            raise ResultStorageUnavailableError(str(error)) from error
        except (RepositoryWriteError, SessionConflictError) as error:
            raise RuntimeError("failed to store collection message") from error

    def record_cycle_result(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Pass session-linked feature and prediction data to the repository."""
        try:
            return self._repository.save_processed_features_and_ml_result(payload)
        except RepositoryConfigurationError as error:
            raise ResultStorageUnavailableError(str(error)) from error
        except RepositoryWriteError as error:
            raise RuntimeError("failed to store cylinder result") from error

    def record_runtime(self, identity, runtime, preview_keep_rows=None):
        """Pi metadata is separate from raw Sensor input and training features."""
        try:
            return self._repository.save_runtime_metadata(
                identity, runtime, preview_keep_rows
            )
        except (RepositoryConfigurationError, RepositoryWriteError) as error:
            raise ResultStorageUnavailableError(
                "runtime persistence unavailable"
            ) from error

    def monitoring(self, cylinder, limit, now=None):
        """Expose only sanitized OPERATION metadata and real Cycle results."""
        from datetime import datetime, timezone

        try:
            stored = self._repository.read_monitoring(cylinder, limit)
        except (RepositoryConfigurationError, RepositoryWriteError) as error:
            raise ResultStorageUnavailableError(
                "monitoring storage unavailable"
            ) from error
        # Rows can arrive during the DB request. Compare against completion,
        # not request-start time; explicit test clocks remain unchanged.
        now = now if now is not None else datetime.now(timezone.utc)
        history = []
        for row in stored["rows"]:
            runtime = row.get("runtime") or {}
            from system.DB.Supabase.cylinder_result_repository import (
                validate_packet_metrics,
            )

            packet_metrics = None
            if "packet_metrics" in runtime:
                try:
                    packet_metrics = validate_packet_metrics(runtime["packet_metrics"])
                except (ValueError, TypeError, OverflowError):
                    pass
            received = runtime.get("last_received_at")
            live = "NO_DATA"
            try:
                moment = datetime.fromisoformat(received)
                if moment.tzinfo is not None:
                    age = (now - moment).total_seconds()
                    if age >= 0:
                        live = "STALE" if age > 10 else "LIVE"
            except (TypeError, ValueError):
                received = None
            history.append(
                {
                    "cylinder_id": cylinder,
                    "session_id": row["session_id"],
                    "sequence_id": row["sequence_id"],
                    "timestamp": row["measured_at"],
                    "measured_at": row["measured_at"],
                    "last_received_at": received,
                    "live_status": live,
                    "sph0645_status": "RECEIVED",
                    "inmp441_status": "RECEIVED",
                    "stft_status": runtime.get("stft_status", "WAITING_FOR_DATA"),
                    "operation_status": runtime.get(
                        "operation_status", "REFERENCE_REQUIRED"
                    ),
                    "ml_status": runtime.get("ml_status", "MODEL_REQUIRED"),
                    "stft_preview": None,
                    "vibration_rms": None,
                    "sound_rms": None,
                    "fft_features": None,
                    "prediction": None,
                    "packet_metrics": packet_metrics,
                }
            )
        latest = dict(history[-1]) if history else None
        if latest:
            feature = stored["features"]
            prediction = stored["prediction"]
            if feature:
                latest.update(
                    vibration_rms=feature["sph0645_rms"],
                    sound_rms=feature["inmp441_rms"],
                    fft_features=feature["fft_features"],
                    feature_timestamp=feature["measured_at"],
                    cycle_id=feature["cycle_id"],
                )
            if prediction:
                latest.update(
                    prediction=prediction["prediction"],
                    prediction_timestamp=prediction["measured_at"],
                    leakage_score=prediction["leakage_score"],
                )
            preview = stored["preview"]
            if preview:
                latest.update(
                    stft_preview=(preview.get("runtime") or {}).get("stft_preview"),
                    stft_preview_timestamp=preview["measured_at"],
                    stft_preview_sequence_id=preview["sequence_id"],
                )
        return {
            "source": "canonical",
            "cylinder_id": cylinder,
            "count": len(history),
            "latest": latest,
            "history": history,
            "live_status": latest["live_status"] if latest else "NO_DATA",
        }

    def load_training_dataset(self) -> list[dict[str, Any]]:
        """Return features that belong to validated labelled training sessions."""
        try:
            return self._repository.load_training_dataset()
        except RepositoryConfigurationError as error:
            raise ResultStorageUnavailableError(str(error)) from error
        except RepositoryWriteError as error:
            raise RuntimeError("failed to load training dataset") from error
