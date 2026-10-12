"""Run the active model on students, persist predictions, raise alerts."""
from __future__ import annotations

import json
import logging

from app.ml.features import LEVEL_ORDER, student_row_to_raw
from app.ml.predict import predict_records
from app.models import alerts as alerts_repo
from app.models import assessments as assessments_repo
from app.models import audit
from app.models import predictions as predictions_repo
from app.models import settings as settings_repo
from app.services.model_service import get_active_artifact
from app.services.observations import build_observations

log = logging.getLogger("trackwell")


class ModelUnavailable(RuntimeError):
    pass


def _create_alerts(student, prediction_id: int, previous, new_level: str):
    """Create alerts for new High risk or a level increase, avoiding duplicates."""
    prev_level = previous["risk_level"] if previous else None
    if prev_level == new_level:
        return None
    if new_level == "High":
        alert_type = "new_high_risk"
        message = f"{student['name']} ({student['student_id']}) is now predicted High Risk" + (
            f" (previously {prev_level})." if prev_level else " (first prediction).")
    elif prev_level and LEVEL_ORDER[new_level] > LEVEL_ORDER[prev_level]:
        alert_type = "risk_increase"
        message = f"{student['name']} ({student['student_id']}) moved from {prev_level} to {new_level} Risk."
    else:
        return None
    if alerts_repo.has_open_alert(student["id"], alert_type, new_level):
        return None
    return alerts_repo.create(student["id"], prediction_id, alert_type, message, prev_level, new_level)


def predict_for_students(student_rows, user_id: int | None) -> dict:
    """Predict risk for the given student rows. Returns a summary dict."""
    version, artifact = get_active_artifact()
    if artifact is None:
        raise ModelUnavailable("No active trained model. Train a model before generating predictions.")
    student_rows = list(student_rows)
    if not student_rows:
        return {"predicted": 0, "alerts": 0, "model_version": version["version"], "counts": {}}

    scores = assessments_repo.scores_for_students([s["id"] for s in student_rows])
    raw_records = [student_row_to_raw(s, scores.get(s["id"])) for s in student_rows]
    results = predict_records(artifact, raw_records)
    settings = settings_repo.get_all()
    global_importance = artifact.get("global_importance", [])[:6]

    counts = {"Low": 0, "Medium": 0, "High": 0}
    alerts_created = 0
    for student, result in zip(student_rows, results):
        previous = predictions_repo.latest_for_student(student["id"])
        explanation = {
            "model_factors": result["model_factors"],
            "observations": build_observations(student, scores.get(student["id"]), settings),
            "global_importance": global_importance,
            "method": "reference_substitution",
            "method_note": (
                "Model-derived factors show how the risk score changes when each indicator is replaced "
                "by the training-set typical value. Observations are descriptive comparisons with the "
                "configured reference levels, not model output."
            ),
        }
        pid = predictions_repo.create(student["id"], version["id"], result["risk_level"],
                                      result["probabilities"], result["risk_score"], explanation)
        if _create_alerts(student, pid, previous, result["risk_level"]):
            alerts_created += 1
        counts[result["risk_level"]] += 1

    audit.log(user_id, "predictions_run", "students", None,
              json.dumps({"count": len(results), "model_version": version["version"], "alerts": alerts_created}))
    return {"predicted": len(results), "alerts": alerts_created, "model_version": version["version"],
            "counts": counts}
