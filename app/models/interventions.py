"""Faculty intervention records."""
from app.db import get_db

TYPES = (
    "Mentoring",
    "Additional Practice",
    "Doubt-Clearing Session",
    "Attendance Follow-up",
    "Counseling Referral",
    "Parent/Guardian Contact",
    "Other",
)
STATUSES = ("Planned", "In Progress", "Completed", "Cancelled")


def get_by_id(pk: int):
    return get_db().execute(
        "SELECT i.*, s.student_id, s.name AS student_name, u.full_name AS faculty_name "
        "FROM interventions i JOIN students s ON s.id = i.student_fk "
        "LEFT JOIN users u ON u.id = i.faculty_user_fk WHERE i.id = ?",
        (pk,),
    ).fetchone()


def list_all(status: str = "", student_fk: int | None = None, overdue_only: bool = False):
    sql = (
        "SELECT i.*, s.student_id, s.name AS student_name, s.class_name, u.full_name AS faculty_name "
        "FROM interventions i JOIN students s ON s.id = i.student_fk "
        "LEFT JOIN users u ON u.id = i.faculty_user_fk WHERE 1 = 1"
    )
    params: list = []
    if status in STATUSES:
        sql += " AND i.status = ?"
        params.append(status)
    if student_fk is not None:
        sql += " AND i.student_fk = ?"
        params.append(student_fk)
    if overdue_only:
        sql += " AND i.follow_up_date IS NOT NULL AND i.follow_up_date < date('now') " \
               "AND i.status IN ('Planned', 'In Progress')"
    sql += " ORDER BY i.intervention_date DESC, i.id DESC"
    return get_db().execute(sql, params).fetchall()


def list_for_student(student_fk: int):
    return list_all(student_fk=student_fk)


def create(data: dict) -> int:
    db = get_db()
    cur = db.execute(
        "INSERT INTO interventions(student_fk, faculty_user_fk, intervention_date, intervention_type, "
        "notes, follow_up_date, status, follow_up_outcome) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (data["student_fk"], data.get("faculty_user_fk"), data["intervention_date"],
         data["intervention_type"], data.get("notes"), data.get("follow_up_date"),
         data["status"], data.get("follow_up_outcome")),
    )
    db.commit()
    return cur.lastrowid


def update(pk: int, data: dict):
    db = get_db()
    db.execute(
        "UPDATE interventions SET intervention_date = ?, intervention_type = ?, notes = ?, "
        "follow_up_date = ?, status = ?, follow_up_outcome = ?, faculty_user_fk = ?, "
        "updated_at = datetime('now') WHERE id = ?",
        (data["intervention_date"], data["intervention_type"], data.get("notes"),
         data.get("follow_up_date"), data["status"], data.get("follow_up_outcome"),
         data.get("faculty_user_fk"), pk),
    )
    db.commit()


def delete(pk: int):
    db = get_db()
    db.execute("DELETE FROM interventions WHERE id = ?", (pk,))
    db.commit()


def status_counts() -> dict:
    rows = get_db().execute("SELECT status, COUNT(*) AS n FROM interventions GROUP BY status").fetchall()
    counts = {s: 0 for s in STATUSES}
    for r in rows:
        counts[r["status"]] = r["n"]
    return counts
