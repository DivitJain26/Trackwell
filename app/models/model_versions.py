"""Trained model versions and their evaluation metadata."""
import json

from app.db import get_db


def list_all():
    return get_db().execute("SELECT * FROM model_versions ORDER BY trained_at DESC, id DESC").fetchall()


def get_by_id(pk: int):
    return get_db().execute("SELECT * FROM model_versions WHERE id = ?", (pk,)).fetchone()


def get_active():
    return get_db().execute("SELECT * FROM model_versions WHERE is_active = 1 LIMIT 1").fetchone()


def next_version_number() -> int:
    row = get_db().execute("SELECT COUNT(*) FROM model_versions").fetchone()
    return int(row[0]) + 1


def create(version: str, algorithm: str, trained_at: str, dataset_source: str, dataset_rows: int,
           metrics: dict, candidates: list, feature_schema: dict, artifact_path: str,
           artifact_sha256: str, notes: str = "", trained_by: int | None = None,
           activate: bool = True) -> int:
    db = get_db()
    if activate:
        db.execute("UPDATE model_versions SET is_active = 0")
    cur = db.execute(
        "INSERT INTO model_versions(version, algorithm, trained_at, trained_by_user_fk, dataset_source, "
        "dataset_rows, metrics_json, candidates_json, feature_schema_json, artifact_path, artifact_sha256, "
        "is_active, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (version, algorithm, trained_at, trained_by, dataset_source, dataset_rows,
         json.dumps(metrics), json.dumps(candidates), json.dumps(feature_schema),
         artifact_path, artifact_sha256, 1 if activate else 0, notes),
    )
    db.commit()
    return cur.lastrowid


def activate(pk: int):
    db = get_db()
    db.execute("UPDATE model_versions SET is_active = 0")
    db.execute("UPDATE model_versions SET is_active = 1 WHERE id = ?", (pk,))
    db.commit()


def parse(row) -> dict | None:
    """Return a model version row as a dict with JSON columns decoded."""
    if row is None:
        return None
    d = dict(row)
    d["metrics"] = json.loads(d.pop("metrics_json"))
    d["candidates"] = json.loads(d.pop("candidates_json"))
    d["feature_schema"] = json.loads(d.pop("feature_schema_json"))
    return d
