from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.ml.artifacts import ArtifactError, load_artifact
from app.ml.features import (ALL_FEATURES, RAW_FEATURES, build_feature_frame, compute_score_trend,
                             student_row_to_raw)
from app.ml.predict import predict_records


def test_feature_frame_is_consistent_between_training_and_inference():
    train = pd.read_csv(Path("data/training_data.csv"))
    Xtrain = build_feature_frame(train)
    # Leakage columns must be removed.
    assert "final_exam_pct" not in Xtrain.columns and "risk_label" not in Xtrain.columns
    assert list(Xtrain.columns) == ALL_FEATURES
    # A single student record (missing quiz_trend) produces the same columns and dtypes.
    raw = student_row_to_raw({"attendance_pct": 60, "previous_gpa": 6.0, "quiz_score": 50, "test_score": 40,
                              "assignment_completion_pct": 55, "study_hours": 1.5, "self_understanding": 3,
                              "participation": "Low", "engagement_level": "Medium"}, quiz_scores=None)
    Xinf = build_feature_frame(pd.DataFrame([raw], columns=RAW_FEATURES))
    assert list(Xinf.columns) == list(Xtrain.columns)
    assert Xinf["attendance_level"].iloc[0] == "Low"
    assert Xinf["avg_score"].iloc[0] == 45.0
    assert np.isnan(Xinf["quiz_trend"].iloc[0])


def test_score_trend():
    assert compute_score_trend(None) is None
    assert compute_score_trend([50.0]) is None
    assert compute_score_trend([50.0, 60.0]) == 10.0
    assert compute_score_trend([60, 60, 40, 40]) == -20.0


def test_training_selects_model_and_prediction_output_format(app, trained_model):
    report = trained_model
    assert report["algorithm"] in ("Logistic Regression", "Random Forest", "Gradient Boosting")
    assert {c["name"] for c in report["candidates"]} == {"Logistic Regression", "Random Forest", "Gradient Boosting"}
    m = report["metrics"]
    for key in ("accuracy", "precision_macro", "recall_macro", "f1_macro", "recall_high", "confusion_matrix"):
        assert key in m
    assert len(m["confusion_matrix"]) == 3
    best = max(report["candidates"], key=lambda c: c["metrics"]["selection_score"])
    assert best["name"] == report["algorithm"]

    artifact = load_artifact(Path(report["artifact_path"]), report["artifact_sha256"])
    weak = {"attendance_pct": 45, "previous_gpa": 4.8, "quiz_score": 30, "test_score": 28,
            "assignment_completion_pct": 35, "study_hours": 0.5, "self_understanding": 1, "quiz_trend": -10,
            "participation": "Low", "engagement_level": "Low"}
    strong = {"attendance_pct": 96, "previous_gpa": 9.2, "quiz_score": 90, "test_score": 88,
              "assignment_completion_pct": 100, "study_hours": 4, "self_understanding": 5, "quiz_trend": None,
              "participation": "High", "engagement_level": "High"}
    results = predict_records(artifact, [weak, strong])
    assert len(results) == 2
    for r in results:
        assert r["risk_level"] in ("Low", "Medium", "High")
        probs = r["probabilities"]
        assert set(probs) == {"Low", "Medium", "High"}
        assert abs(sum(probs.values()) - 1.0) < 1e-6
        assert 0 <= r["risk_score"] <= 100
        assert r["model_factors"] and {"feature", "label", "value", "contribution", "direction"} <= set(r["model_factors"][0])
    assert results[0]["risk_score"] > results[1]["risk_score"]
    assert results[0]["risk_level"] == "High" and results[1]["risk_level"] == "Low"


def test_tampered_artifact_is_refused(app, trained_model):
    path = Path(trained_model["artifact_path"])
    with open(path, "ab") as fh:
        fh.write(b"tamper")
    with pytest.raises(ArtifactError):
        load_artifact(path, trained_model["artifact_sha256"])
    with pytest.raises(ArtifactError):
        load_artifact(path.with_name("missing.joblib"), trained_model["artifact_sha256"])


def test_prediction_route_without_model_shows_message(client, auth, student_pk):
    auth.as_faculty()
    r = client.post(f"/students/{student_pk}/predict", follow_redirects=True)
    assert b"No active trained model" in r.data
    r = client.get("/predictions/")
    assert b"No trained model is active" in r.data


def test_prediction_route_stores_prediction_and_explanation(client, auth, app, student_pk, trained_model):
    auth.as_faculty()
    r = client.post(f"/students/{student_pk}/predict", follow_redirects=True)
    assert b"Prediction generated" in r.data
    with app.app_context():
        from app.models import predictions
        p = predictions.latest_for_student(student_pk)
        assert p["risk_level"] == "High"
        exp = predictions.parse_explanation(p)
        assert exp["model_factors"] and exp["observations"]
        assert any(o["code"] == "low_attendance" for o in exp["observations"])
        assert p["model_version"] == trained_model["version"]
    r = client.get(f"/students/{student_pk}")
    assert b"High Risk" in r.data and b"Model-derived contributing factors" in r.data
