"""Connect parsed Pico sensor payloads to the existing three saved models."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

from .analysis import MODEL_FEATURE_NAMES, CycleFeatureExtractor, PREPROCESSING_VERSION

LIFE_FEATURE_NAMES = (
    "vibration_prediction",
    "vibration_confidence",
    "sound_prediction",
    "sound_confidence",
)


class ModelContractError(RuntimeError):
    """Raised when a saved model does not match its approved input contract."""


def load_existing_three_model_engine(model_project_path=None):
    """Load the existing ML-cylinder engine without copying its model logic."""
    configured_path = model_project_path or os.environ.get(
        "SMART_CYLINDER_MODEL_PROJECT"
    )
    if configured_path is None:
        configured_path = Path(__file__).resolve().parents[3] / "ML-cylinder"
    project_path = Path(configured_path).expanduser().resolve()
    module_path = project_path / "src" / "three_model_inference.py"
    if not module_path.is_file():
        raise FileNotFoundError("three-model inference module was not found")

    spec = importlib.util.spec_from_file_location(
        "smart_cylinder_three_model_inference",
        module_path,
    )
    if spec is None or spec.loader is None:
        raise ImportError("three-model inference module could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ThreeModelInference()


class RealtimeInference:
    """Run saved-model inference only after MQTT parsing and duplicate gating."""

    def __init__(
        self,
        inference_engine=None,
        inference_engine_factory=load_existing_three_model_engine,
        feature_extractor=None,
        output=print,
    ):
        self._engine = inference_engine
        self._engine_factory = inference_engine_factory
        self._feature_extractor = feature_extractor or CycleFeatureExtractor()
        self._output = output
        self._contract_checked = False
        self.last_error = None
        self.last_result = None

    def handle_message(self, payload, is_duplicate=False):
        """MQTT subscriber callback that isolates every ML failure."""
        if is_duplicate:
            return None
        try:
            result = self.process_parsed_payload(payload)
        except Exception as error:
            self.last_error = {
                "type": type(error).__name__,
                "message": str(error),
            }
            self._output(
                "[INFERENCE] FAILED: %s: %s"
                % (self.last_error["type"], self.last_error["message"])
            )
            return None
        self.last_error = None
        self.last_result = result
        return result

    def process_parsed_payload(self, payload):
        """Create ordered features and call all three existing saved models."""
        self._validate_parser_output(payload)
        cylinder_id = payload["cylinder_id"]
        sph0645_samples = payload["sph0645"]["samples"]
        inmp441_samples = payload["inmp441"]["samples"]

        self._output("[MQTT] %s received" % cylinder_id)
        self._output("[PARSER] OK")
        self._output("[PCM] SPH0645=%d" % len(sph0645_samples))
        self._output("[PCM] INMP441=%d" % len(inmp441_samples))

        feature_sets = self._feature_extractor.extract_model_features(
            sph0645_samples,
            inmp441_samples,
        )
        self._print_features("VIBRATION", feature_sets["vibration"])
        self._print_features("SOUND", feature_sets["sound"])

        engine = self._get_engine()
        if not self._contract_checked:
            self._validate_engine_contract(engine)
            self._contract_checked = True

        result = engine.predict(
            feature_sets["vibration"],
            feature_sets["sound"],
        )
        self._output("[MODEL 1] OK → %s" % result["vibration"]["prediction"])
        self._output("[MODEL 2] OK → %s" % result["sound"]["prediction"])
        self._output("[MODEL 3] OK → %s" % result["health_score"])
        self._output("[INFERENCE] COMPLETE")
        return {
            "cylinder_id": cylinder_id,
            "session_id": payload["session_id"],
            "sequence_id": payload["sequence_id"],
            "timestamp": payload["timestamp"],
            "features": feature_sets,
            "inference": result,
        }

    def model_input_metadata(self):
        """Return verified names, order, shape and preprocessing information."""
        engine = self._get_engine()
        self._validate_engine_contract(engine)
        return {
            "model_1": self._model_metadata(engine.vibration),
            "model_2": self._model_metadata(engine.sound),
            "model_3": self._model_metadata(engine.rul),
        }

    def _get_engine(self):
        if self._engine is None:
            if self._engine_factory is None:
                raise RuntimeError("an inference engine is required")
            self._engine = self._engine_factory()
        return self._engine

    def _validate_parser_output(self, payload):
        if not isinstance(payload, dict) or "duplicate_key" not in payload:
            raise ValueError("input must be the system MQTT Parser output")
        for sensor_name in ("sph0645", "inmp441"):
            chunk = payload.get(sensor_name)
            if not isinstance(chunk, dict) or "samples" not in chunk:
                raise ValueError("%s PCM samples are missing" % sensor_name)

    def _validate_engine_contract(self, engine):
        if getattr(engine, "preprocessing_version", None) != PREPROCESSING_VERSION:
            raise ModelContractError(
                "MODEL_REQUIRED: mean-removal preprocessing contract mismatch"
            )
        contracts = (
            ("model 1", engine.vibration, MODEL_FEATURE_NAMES),
            ("model 2", engine.sound, MODEL_FEATURE_NAMES),
            ("model 3", engine.rul, LIFE_FEATURE_NAMES),
        )
        for label, predictor, expected_names in contracts:
            actual_names = tuple(getattr(predictor, "feature_names", ()))
            if actual_names != tuple(expected_names):
                raise ModelContractError(
                    "%s feature order mismatch: expected=%s actual=%s"
                    % (label, tuple(expected_names), actual_names)
                )
            model = getattr(predictor, "model", None)
            feature_count = getattr(model, "n_features_in_", None)
            if feature_count is not None and feature_count != len(expected_names):
                raise ModelContractError(
                    "%s input shape mismatch: expected=(1, %d) actual_features=%s"
                    % (label, len(expected_names), feature_count)
                )
            if not self._contains_class(model, "StandardScaler"):
                raise ModelContractError(
                    "%s saved StandardScaler preprocessing was not found" % label
                )

    def _model_metadata(self, predictor):
        names = tuple(predictor.feature_names)
        return {
            "feature_names": names,
            "feature_order": names,
            "input_shape": (1, len(names)),
            "scaler": "saved StandardScaler",
            "preprocessing": "saved model pipeline",
        }

    def _print_features(self, label, features):
        self._output("[FEATURE] %s" % label)
        for index, name in enumerate(MODEL_FEATURE_NAMES, start=1):
            self._output("%02d. %s = %s" % (index, name, features[name]))

    @staticmethod
    def _contains_class(root, class_name):
        pending = [root]
        visited = set()
        while pending:
            value = pending.pop()
            if value is None or id(value) in visited:
                continue
            visited.add(id(value))
            if value.__class__.__name__ == class_name:
                return True
            if isinstance(value, dict):
                pending.extend(value.values())
                continue
            if isinstance(value, (list, tuple)):
                for item in value:
                    if isinstance(item, tuple) and len(item) == 2:
                        pending.append(item[1])
                    else:
                        pending.append(item)
                continue
            for attribute in (
                "steps",
                "named_steps",
                "transformer",
                "transformer_",
            ):
                nested = getattr(value, attribute, None)
                if nested is not None:
                    pending.append(nested)
        return False
