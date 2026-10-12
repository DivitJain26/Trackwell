"""Dashboard alerts for newly identified or increasing risk."""
from app.db import get_db


def list_alerts(status: str = "", limit: int = 200):
    sql = (
        "SELECT a.*, s.student_id, s.name, s.class_name, s.semester, u.full_name AS reviewed_by_name "
        "FROM alerts a JOIN students s ON s.id = a.student_fk "
        "LEFT JOIN users u ON u.id = a.reviewed_by_fk WHERE 1 = 1"
    )
    params: list = []
    if status in ("new", "reviewed"):
        sql += " AND a.status = ?"
        params.append(status)
    sql += " ORDER BY a.created_at DESC, a.id DESC LIMIT ?"
    params.append(limit)
    return get_db().execute(sql, params).fetchall()


def list_for_student(student_fk: int):
    return get_db().execute(
        "SELECT a.*, u.full_name AS reviewed_by_name FROM alerts a "
        "LEFT JOIN users u ON u.id = a.reviewed_by_fk WHERE a.student_fk = ? "
        "ORDER BY a.created_at DESC",
        (student_fk,),
    ).fetchall()


def get_by_id(pk: int):
    return get_db().execute(
        "SELECT a.*, s.student_id, s.name FROM alerts a JOIN students s ON s.id = a.student_fk "
        "WHERE a.id = ?", (pk,)
    ).fetchone()


def count_new() -> int:
    return get_db().execute("SELECT COUNT(*) FROM alerts WHERE status = 'new'").fetchone()[0]


def has_open_alert(student_fk: int, alert_type: str, new_level: str) -> bool:
    row = get_db().execute(
        "SELECT 1 FROM alerts WHERE student_fk = ? AND alert_type = ? AND new_level = ? AND status = 'new'",
        (student_fk, alert_type, new_level),
    ).fetchone()
    return row is not None


def create(student_fk: int, prediction_fk: int, alert_type: str, message: str,
           previous_level: str | None, new_level: str) -> int:
    db = get_db()
    cur = db.execute(
        "INSERT INTO alerts(student_fk, prediction_fk, alert_type, message, previous_level, new_level) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (student_fk, prediction_fk, alert_type, message, previous_level, new_level),
    )
    db.commit()
    return cur.lastrowid


def mark_reviewed(pk: int, user_id: int, intervention_fk: int | None = None):
    db = get_db()
    db.execute(
        "UPDATE alerts SET status = 'reviewed', reviewed_by_fk = ?, reviewed_at = datetime('now'), "
        "intervention_fk = COALESCE(?, intervention_fk) WHERE id = ?",
        (user_id, intervention_fk, pk),
    )
    db.commit()


def link_intervention(pk: int, intervention_fk: int):
    db = get_db()
    db.execute("UPDATE alerts SET intervention_fk = ? WHERE id = ?", (intervention_fk, pk))
    db.commit()
