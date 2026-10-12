"""Model lifecycle: training through the app, loading the active artifact, status."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from flask import current_app

from app.ml.artifacts import ArtifactError, load_artifact
from app.ml.train import TrainingError, train_and_evaluate
from app.models import audit, model_versions

log = logging.getLogger("trackwell")

_cache: dict = {"key": None, "artifact": None}


def train_new_version(user_id: int | None, quick: bool = False, notes: str = "",
                      csv_path: Path | None = None) -> dict:
    csv_path = Path(csv_path or current_app.config["TRAINING_DATA"])
    version = f"v{model_versions.next_version_number()}"
    # Guard against a version collision if a row was deleted manually.
    existing = {r["version"] for r in model_versions.list_all()}
    n = model_versions.next_version_number()
    while version in existing:
        n += 1
        version = f"v{n}"
    report = train_and_evaluate(csv_path, Path(current_app.config["MODEL_DIR"]), version,
                                quick=quick, dataset_source=csv_path.name)
    metrics = dict(report["metrics"])
    metrics["global_importance"] = report["global_importance"]
    metrics["class_distribution"] = report["class_distribution"]
    metrics["train_rows"] = report["train_rows"]
    metrics["test_rows"] = report["test_rows"]
    metrics["selection_rule"] = report["selection_rule"]
    metrics["sklearn_version"] = report["sklearn_version"]
    pk = model_versions.create(
        version=version, algorithm=report["algorithm"], trained_at=report["trained_at"],
        dataset_source=report["dataset_source"], dataset_rows=report["dataset_rows"],
        metrics=metrics, candidates=report["candidates"], feature_schema=report["feature_schema"],
        artifact_path=report["artifact_path"], artifact_sha256=report["artifact_sha256"],
        notes=notes, trained_by=user_id, activate=True,
    )
    _cache["key"] = None
    audit.log(user_id, "model_trained", "model_version", pk,
              json.dumps({"version": version, "algorithm": report["algorithm"]}))
    report["id"] = pk
    return report


def get_active_artifact():
    """Return ``(model_version_dict, artifact)`` or ``(None, None)`` if unavailable.

    Raises :class:`ArtifactError` if the recorded artifact cannot be trusted.
    """
    row = model_versions.get_active()
    if row is None:
        return None, None
    key = (row["id"], row["artifact_sha256"])
    if _cache["key"] != key:
        _cache["artifact"] = load_artifact(Path(row["artifact_path"]), row["artifact_sha256"])
        _cache["key"] = key
    return model_versions.parse(row), _cache["artifact"]


def model_status() -> dict:
    """Summarise model availability for the UI without raising."""
    row = model_versions.get_active()
    if row is None:
        return {"available": False, "message": "No trained model is active. Train a model from the Model page.",
                "version": None}
    try:
        load_artifact(Path(row["artifact_path"]), row["artifact_sha256"])
    except ArtifactError as exc:
        return {"available": False, "message": str(exc), "version": row["version"]}
    return {"available": True, "message": "", "version": row["version"], "algorithm": row["algorithm"],
            "trained_at": row["trained_at"]}


__all__ = ["train_new_version", "get_active_artifact", "model_status", "ArtifactError", "TrainingError"]
