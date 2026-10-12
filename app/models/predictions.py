"""Stored risk predictions."""
import json

from app.db import get_db


def latest_for_student(student_fk: int):
    return get_db().execute(
        "SELECT p.*, mv.version AS model_version, mv.algorithm FROM predictions p "
        "JOIN model_versions mv ON mv.id = p.model_version_fk "
        "WHERE p.student_fk = ? ORDER BY p.created_at DESC, p.id DESC LIMIT 1",
        (student_fk,),
    ).fetchone()


def history_for_student(student_fk: int, limit: int = 20):
    return get_db().execute(
        "SELECT p.*, mv.version AS model_version FROM predictions p "
        "JOIN model_versions mv ON mv.id = p.model_version_fk "
        "WHERE p.student_fk = ? ORDER BY p.created_at DESC, p.id DESC LIMIT ?",
        (student_fk, limit),
    ).fetchall()


def create(student_fk: int, model_version_fk: int, risk_level: str, probs: dict,
           risk_score: float, explanation: dict) -> int:
    db = get_db()
    cur = db.execute(
        "INSERT INTO predictions(student_fk, model_version_fk, risk_level, prob_low, prob_medium, "
        "prob_high, risk_score, explanation_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (student_fk, model_version_fk, risk_level, probs["Low"], probs["Medium"], probs["High"],
         risk_score, json.dumps(explanation)),
    )
    db.commit()
    return cur.lastrowid


def latest_all(class_name: str = "", semester: str = "", risk_level: str = ""):
    """Latest prediction per student, joined with student info."""
    sql = """
        SELECT p.*, mv.version AS model_version, s.student_id, s.name, s.class_name, s.semester,
               s.attendance_pct, s.assignment_completion_pct
        FROM predictions p
        JOIN model_versions mv ON mv.id = p.model_version_fk
        JOIN students s ON s.id = p.student_fk
        WHERE p.id = (SELECT id FROM predictions WHERE student_fk = p.student_fk
                      ORDER BY created_at DESC, id DESC LIMIT 1)
    """
    params: list = []
    if class_name:
        sql += " AND s.class_name = ?"
        params.append(class_name)
    if semester:
        sql += " AND s.semester = ?"
        params.append(int(semester))
    if risk_level:
        sql += " AND p.risk_level = ?"
        params.append(risk_level)
    sql += " ORDER BY p.risk_score DESC, s.student_id"
    return get_db().execute(sql, params).fetchall()


def risk_counts() -> dict:
    rows = get_db().execute(
        "SELECT p.risk_level, COUNT(*) AS n FROM predictions p "
        "WHERE p.id = (SELECT id FROM predictions WHERE student_fk = p.student_fk "
        "ORDER BY created_at DESC, id DESC LIMIT 1) GROUP BY p.risk_level"
    ).fetchall()
    counts = {"Low": 0, "Medium": 0, "High": 0}
    for r in rows:
        counts[r["risk_level"]] = r["n"]
    return counts


def last_prediction_time():
    row = get_db().execute("SELECT MAX(created_at) FROM predictions").fetchone()
    return row[0]


def parse_explanation(row) -> dict:
    try:
        return json.loads(row["explanation_json"])
    except (KeyError, TypeError, ValueError):
        return {}
