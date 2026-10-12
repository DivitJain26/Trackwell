"""Student records."""
from app.db import get_db

# Column order used everywhere a student record is written or exported.
FIELDS = [
    "student_id", "name", "class_name", "semester", "attendance_pct", "previous_gpa",
    "quiz_score", "test_score", "assignment_completion_pct", "study_hours",
    "participation", "engagement_level", "self_understanding",
]

LEVELS = ("Low", "Medium", "High")


def count() -> int:
    return get_db().execute("SELECT COUNT(*) FROM students").fetchone()[0]


def get_by_id(pk: int):
    return get_db().execute("SELECT * FROM students WHERE id = ?", (pk,)).fetchone()


def get_by_student_id(student_id: str):
    return get_db().execute(
        "SELECT * FROM students WHERE student_id = ?", (student_id.strip(),)
    ).fetchone()


def distinct_classes():
    return [r[0] for r in get_db().execute(
        "SELECT DISTINCT class_name FROM students ORDER BY class_name").fetchall()]


def distinct_semesters():
    return [r[0] for r in get_db().execute(
        "SELECT DISTINCT semester FROM students ORDER BY semester").fetchall()]


def search(query: str = "", class_name: str = "", semester: str = "", risk_level: str = "",
           sort: str = "student_id", limit: int | None = None):
    """Return students joined with their latest prediction (if any)."""
    sql = """
        SELECT s.*, p.risk_level, p.risk_score, p.prob_high, p.created_at AS predicted_at,
               mv.version AS model_version
        FROM students s
        LEFT JOIN predictions p ON p.id = (
            SELECT id FROM predictions WHERE student_fk = s.id ORDER BY created_at DESC, id DESC LIMIT 1
        )
        LEFT JOIN model_versions mv ON mv.id = p.model_version_fk
        WHERE 1 = 1
    """
    params: list = []
    if query:
        sql += " AND (s.student_id LIKE ? OR s.name LIKE ?)"
        like = f"%{query.strip()}%"
        params += [like, like]
    if class_name:
        sql += " AND s.class_name = ?"
        params.append(class_name)
    if semester:
        sql += " AND s.semester = ?"
        params.append(int(semester))
    if risk_level:
        if risk_level == "none":
            sql += " AND p.id IS NULL"
        elif risk_level in LEVELS:
            sql += " AND p.risk_level = ?"
            params.append(risk_level)
    order_by = {
        "student_id": "s.student_id",
        "name": "s.name",
        "attendance": "s.attendance_pct",
        "risk": "CASE p.risk_level WHEN 'High' THEN 0 WHEN 'Medium' THEN 1 WHEN 'Low' THEN 2 ELSE 3 END, p.risk_score DESC",
    }.get(sort, "s.student_id")
    sql += f" ORDER BY {order_by}"
    if limit:
        sql += " LIMIT ?"
        params.append(int(limit))
    return get_db().execute(sql, params).fetchall()


def list_all():
    return get_db().execute("SELECT * FROM students ORDER BY student_id").fetchall()


def create(data: dict) -> int:
    db = get_db()
    cols = ", ".join(FIELDS)
    marks = ", ".join("?" for _ in FIELDS)
    cur = db.execute(
        f"INSERT INTO students({cols}) VALUES ({marks})",
        [data.get(f) for f in FIELDS],
    )
    db.commit()
    return cur.lastrowid


def update(pk: int, data: dict):
    db = get_db()
    assignments = ", ".join(f"{f} = ?" for f in FIELDS)
    db.execute(
        f"UPDATE students SET {assignments}, updated_at = datetime('now') WHERE id = ?",
        [data.get(f) for f in FIELDS] + [pk],
    )
    db.commit()


def upsert_by_student_id(data: dict) -> tuple[int, str]:
    """Insert or update by student_id. Returns (pk, 'inserted'|'updated')."""
    existing = get_by_student_id(data["student_id"])
    if existing:
        update(existing["id"], data)
        return existing["id"], "updated"
    return create(data), "inserted"


def delete(pk: int):
    db = get_db()
    db.execute("DELETE FROM students WHERE id = ?", (pk,))
    db.commit()


def summary_stats() -> dict:
    row = get_db().execute(
        "SELECT COUNT(*) AS total, AVG(attendance_pct) AS avg_attendance, "
        "AVG(assignment_completion_pct) AS avg_assignment, "
        "SUM(CASE WHEN attendance_pct < ? THEN 1 ELSE 0 END) AS low_attendance "
        "FROM students",
        (75,),
    ).fetchone()
    return dict(row)
