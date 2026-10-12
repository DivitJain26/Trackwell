"""Inference and model-derived explanations for individual students."""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.ml.features import FEATURE_LABELS, RAW_CATEGORICAL, RAW_FEATURES, RAW_NUMERIC, build_feature_frame

# Risk score: a single 0-100 number summarising the class probabilities.
# score = 100 * (0.5 * P(Medium) + 1.0 * P(High))
MEDIUM_WEIGHT = 0.5


def risk_score_from_probs(probs: dict) -> float:
    return float(100.0 * (MEDIUM_WEIGHT * probs.get("Medium", 0.0) + probs.get("High", 0.0)))


def _probabilities(pipeline, classes, frame: pd.DataFrame) -> np.ndarray:
    """Return probabilities ordered as Low, Medium, High."""
    proba = pipeline.predict_proba(frame)
    order = [list(classes).index(c) for c in ("Low", "Medium", "High")]
    return proba[:, order]


def predict_records(artifact: dict, raw_records: list[dict]) -> list[dict]:
    """Predict risk for a list of raw student dicts (see features.student_row_to_raw).

    Each result contains the predicted level (argmax of class probabilities),
    the three class probabilities, the 0-100 risk score and the top
    model-derived contributing factors.
    """
    if not raw_records:
        return []
    pipeline = artifact["pipeline"]
    classes = artifact["classes"]
    reference = artifact["reference_values"]

    raw_df = pd.DataFrame(raw_records, columns=RAW_FEATURES)
    frame = build_feature_frame(raw_df)
    proba = _probabilities(pipeline, classes, frame)
    base_scores = MEDIUM_WEIGHT * proba[:, 1] + proba[:, 2]

    # Local attribution by reference substitution: replace one raw feature at a
    # time with its training-set median/mode and measure how the risk score
    # moves. A positive contribution means the student's actual value pushes
    # the prediction towards higher risk compared with a typical student.
    contributions = np.zeros((len(raw_df), len(RAW_FEATURES)))
    for j, feat in enumerate(RAW_FEATURES):
        ref_val = reference.get(feat)
        if ref_val is None:
            continue
        altered = raw_df.copy()
        altered[feat] = ref_val
        alt_proba = _probabilities(pipeline, classes, build_feature_frame(altered))
        alt_scores = MEDIUM_WEIGHT * alt_proba[:, 1] + alt_proba[:, 2]
        contributions[:, j] = base_scores - alt_scores

    results = []
    for i, rec in enumerate(raw_records):
        probs = {"Low": float(proba[i, 0]), "Medium": float(proba[i, 1]), "High": float(proba[i, 2])}
        level = max(probs, key=probs.get)
        factors = []
        for j, feat in enumerate(RAW_FEATURES):
            c = float(contributions[i, j])
            value = rec.get(feat)
            if value is None or (isinstance(value, float) and np.isnan(value)):
                continue
            factors.append({
                "feature": feat,
                "label": FEATURE_LABELS.get(feat, feat),
                "value": value,
                "reference": reference.get(feat),
                "contribution": round(c * 100, 2),  # in risk-score points
                "direction": "increases_risk" if c > 0 else ("reduces_risk" if c < 0 else "neutral"),
            })
        factors.sort(key=lambda f: abs(f["contribution"]), reverse=True)
        results.append({
            "risk_level": level,
            "probabilities": probs,
            "risk_score": round(risk_score_from_probs(probs), 2),
            "model_factors": factors[:6],
        })
    return results
