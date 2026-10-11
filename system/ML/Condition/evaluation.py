"""Evaluate labelled condition predictions without fitting or running a model."""

from collections import Counter
from collections.abc import Mapping


def _label(value):
    if not isinstance(value, str):
        return None
    value = value.strip().upper()
    if value == "NORMAL":
        return "NORMAL"
    if value in {
        "ABNORMAL",
        "SEAL_LEAK",
        "PRESSURE_DROP",
        "PRESSURE_LOW",
        "INTERNAL_WEAR",
    }:
        return "ABNORMAL"
    return None


def _ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def evaluate_predictions(rows, *, training_session_ids=None):
    """Return binary metrics plus explicit coverage and evaluation provenance.

    Each row requires a unique sample_id and session_id. Ground Truth is
    supplied separately from prediction; unknown labels are never inferred.
    Rates use [0, 1]; undefined denominators return None (JSON null).
    """
    counts = Counter()
    seen = set()
    sessions = set()
    tp = fp = tn = fn = 0
    for row in rows:
        counts["total"] += 1
        if not isinstance(row, Mapping):
            raise ValueError("evaluation rows must be objects")
        sample = row.get("sample_id")
        session = row.get("session_id")
        if not isinstance(sample, str) or not sample.strip():
            raise ValueError("sample_id must be a non-empty string")
        if not isinstance(session, str) or not session.strip():
            raise ValueError("session_id must be a non-empty string")
        key = (session, sample)
        if key in seen:
            raise ValueError("duplicate evaluation sample")
        seen.add(key)
        sessions.add(session)
        truth = _label(row.get("ground_truth"))
        if truth is None:
            counts["unknown_ground_truth"] += 1
            continue
        counts["labelled"] += 1
        status = row.get("inference_status", "OK")
        if status == "ERROR":
            counts["inference_errors"] += 1
            continue
        if status == "ABSTAIN":
            counts["abstentions"] += 1
            continue
        if status != "OK":
            raise ValueError("inference_status must be OK, ERROR or ABSTAIN")
        prediction = _label(row.get("prediction"))
        if prediction is None:
            counts["invalid_predictions"] += 1
            continue
        counts["evaluated"] += 1
        tp += truth == "ABNORMAL" and prediction == "ABNORMAL"
        fn += truth == "ABNORMAL" and prediction == "NORMAL"
        fp += truth == "NORMAL" and prediction == "ABNORMAL"
        tn += truth == "NORMAL" and prediction == "NORMAL"
    evaluated = counts["evaluated"]
    overlap = None
    if training_session_ids is not None:
        if isinstance(training_session_ids, (str, bytes)):
            raise ValueError("training_session_ids must be a sequence of strings")
        training = set(training_session_ids)
        if any(not isinstance(s, str) or not s.strip() for s in training):
            raise ValueError("training session IDs must be non-empty strings")
        overlap = sorted(sessions & training)
    warnings = []
    if overlap is None:
        warnings.append("TRAINING_SESSION_OVERLAP_UNKNOWN")
    elif overlap:
        warnings.append("TRAINING_SESSION_OVERLAP")
    if not (tp + fn) or not (tn + fp):
        warnings.append("BOTH_CLASSES_NOT_EVALUATED")
    if counts["labelled"] != evaluated:
        warnings.append("INCOMPLETE_PREDICTION_COVERAGE")
    if counts["unknown_ground_truth"]:
        warnings.append("UNKNOWN_GROUND_TRUTH_EXCLUDED")
    return {
        "status": "EVALUATED" if evaluated else "NO_EVALUABLE_PREDICTIONS",
        "evaluation_scope": "EXPLORATORY",
        "scope_note": "Session separation alone does not verify label provenance, cylinder independence or generalization.",
        "rate_unit": "fraction_0_to_1",
        "counts": {
            name: counts[name]
            for name in (
                "total",
                "labelled",
                "evaluated",
                "unknown_ground_truth",
                "inference_errors",
                "abstentions",
                "invalid_predictions",
            )
        },
        "confusion_matrix": {"tp": tp, "fn": fn, "fp": fp, "tn": tn},
        "metrics": {
            "accuracy": _ratio(tp + tn, evaluated),
            "precision": _ratio(tp, tp + fp),
            "abnormal_recall": _ratio(tp, tp + fn),
            "false_alarm_rate": _ratio(fp, fp + tn),
            "f1": _ratio(2 * tp, 2 * tp + fp + fn),
            "prediction_coverage": _ratio(evaluated, counts["labelled"]),
            "correct_per_labelled_sample": _ratio(tp + tn, counts["labelled"]),
        },
        "sessions": sorted(sessions),
        "training_session_overlap": overlap,
        "warnings": warnings,
    }
