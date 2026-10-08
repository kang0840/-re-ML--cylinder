"""Real lifecycle data only: validated, subject-separated Weibull-AFT pipeline."""

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class LifecycleConfig:
    feature_names: tuple
    subject_field: str
    duration_field: str
    event_field: str
    test_fraction: float
    random_seed: int
    min_train_subjects: int
    min_train_events: int
    fitter_kwargs: dict

    def __post_init__(self):
        fields = (self.subject_field, self.duration_field, self.event_field)
        if not self.feature_names or len(set(self.feature_names)) != len(
            self.feature_names
        ):
            raise ValueError("unique feature names are required")
        if len(set(fields)) != 3 or set(fields) & set(self.feature_names):
            raise ValueError("identity, outcome and feature fields must be disjoint")
        if not 0 < self.test_fraction < 1:
            raise ValueError("test_fraction must be between zero and one")
        if self.min_train_subjects < 2 or self.min_train_events < 1:
            raise ValueError("training requirements must be explicit and positive")


class WeibullPipeline:
    """Accept repository-loaded rows; never invent event times or censored outcomes.

    One row per lifecycle subject is required. Features must be known at the
    externally defined prediction origin, not aggregated using future failure
    information. duration is observed time from that same origin in one unit.
    """

    def __init__(self, config, fitter_factory=None):
        self.config = config
        self.fitter_factory = fitter_factory
        self.model = None
        self.status = "DATA_REQUIRED"

    def validate(self, rows):
        import pandas as pd

        cfg = self.config
        required = [
            cfg.subject_field,
            cfg.duration_field,
            cfg.event_field,
            *cfg.feature_names,
        ]
        frame = pd.DataFrame(rows)
        if frame.empty:
            return frame
        if any(name not in frame for name in required):
            raise ValueError("required lifecycle fields are missing")
        frame = frame[required].copy()
        if (
            frame[cfg.subject_field].isna().any()
            or frame[cfg.subject_field].duplicated().any()
        ):
            raise ValueError("one non-null row per lifecycle subject is required")
        for name in (cfg.duration_field, *cfg.feature_names):
            if any(isinstance(v, (bool, str)) for v in frame[name]):
                raise ValueError("lifecycle numeric fields must contain numbers")
            if frame[name].isna().any() or not all(
                isfinite(float(v)) for v in frame[name]
            ):
                raise ValueError("lifecycle fields must be finite")
        if (frame[cfg.duration_field] <= 0).any():
            raise ValueError("observed durations must be positive")
        if not frame[cfg.event_field].isin([0, 1]).all():
            raise ValueError("event must be zero (censored) or one (observed failure)")
        return frame

    def train_from_repository(self, loader):
        """loader performs the approved DB read and lifecycle aggregation."""
        return self.train(loader())

    def train(self, rows):
        self.model = None
        frame = self.validate(rows)
        if frame.empty:
            self.status = "DATA_REQUIRED"
            return {"status": self.status}
        cfg = self.config
        from sklearn.model_selection import train_test_split

        if len(frame) < cfg.min_train_subjects + 2:
            self.status = "TRAINING_NOT_AVAILABLE"
            return {"status": self.status}
        train, test = train_test_split(
            frame, test_size=cfg.test_fraction, random_state=cfg.random_seed
        )
        if (
            len(train) < cfg.min_train_subjects
            or train[cfg.event_field].sum() < cfg.min_train_events
        ):
            self.status = "TRAINING_NOT_AVAILABLE"
            return {"status": self.status}
        factory = self.fitter_factory
        if factory is None:
            try:
                from lifelines import WeibullAFTFitter
            except ImportError:
                self.status = "DEPENDENCY_REQUIRED"
                return {"status": self.status}
            factory = WeibullAFTFitter
        try:
            model = factory(**cfg.fitter_kwargs)
            model.fit(
                train.drop(columns=[cfg.subject_field]),
                duration_col=cfg.duration_field,
                event_col=cfg.event_field,
            )
            metrics = self._evaluate(model, test)
        except Exception as error:
            self.status = "TRAINING_NOT_AVAILABLE"
            return {"status": self.status, "error_type": type(error).__name__}
        self.model = model
        self.status = "TRAINED"
        return {
            "status": self.status,
            "train_subjects": len(train),
            "test_subjects": len(test),
            **metrics,
        }

    def _evaluate(self, model, test):
        from lifelines.utils import concordance_index
        import numpy as np

        cfg = self.config
        predictions = np.asarray(
            model.predict_median(test[list(cfg.feature_names)]), dtype=float
        )
        if not np.isfinite(predictions).all() or (predictions <= 0).any():
            raise ValueError("invalid predicted lifetimes")
        try:
            score = float(
                concordance_index(
                    test[cfg.duration_field], predictions, test[cfg.event_field]
                )
            )
        except ZeroDivisionError:
            score = None
        observed = test[cfg.event_field].to_numpy() == 1
        mae = (
            float(
                np.mean(
                    np.abs(
                        test[cfg.duration_field].to_numpy()[observed]
                        - predictions[observed]
                    )
                )
            )
            if observed.any()
            else None
        )
        return {
            "c_index": score,
            "mae_observed_failures_only": mae,
            "evaluation_status": (
                "EVALUATED" if score is not None else "NO_COMPARABLE_PAIRS"
            ),
        }

    def predict(self, feature_rows):
        if self.model is None:
            return {"status": "TRAINING_NOT_AVAILABLE"}
        import pandas as pd

        frame = pd.DataFrame(feature_rows)
        names = list(self.config.feature_names)
        if frame.empty or any(name not in frame for name in names):
            raise ValueError("required prediction features are missing")
        for name in names:
            if not all(
                not isinstance(v, (bool, str)) and isfinite(float(v))
                for v in frame[name]
            ):
                raise ValueError("prediction features must be finite numbers")
        predictions = self.model.predict_median(frame[names])
        if not all(isfinite(float(v)) and v > 0 for v in predictions):
            raise ValueError("invalid predicted lifetimes")
        return {
            "status": "PREDICTED",
            "median_duration_from_prediction_origin": predictions.tolist(),
        }

    def coefficient_confidence_intervals(self):
        if self.model is None:
            return {"status": "TRAINING_NOT_AVAILABLE"}
        return self.model.confidence_intervals_.copy()
