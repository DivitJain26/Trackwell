"""Historical assessment scores used for trend features."""
from app.db import get_db

TYPES = ("quiz", "test", "assignment")


def list_for_student(student_fk: int):
    return get_db().execute(
        "SELECT * FROM assessments WHERE student_fk = ? ORDER BY recorded_on, id",
        (student_fk,),
    ).fetchall()


def scores_for_students(student_fks: list[int]) -> dict[int, list[float]]:
    """Return {student_fk: [quiz/test score_pct in chronological order]}."""
    if not student_fks:
        return {}
    marks = ",".join("?" for _ in student_fks)
    rows = get_db().execute(
        f"SELECT student_fk, score_pct FROM assessments "
        f"WHERE student_fk IN ({marks}) AND assessment_type IN ('quiz', 'test') "
        f"ORDER BY student_fk, recorded_on, id",
        list(student_fks),
    ).fetchall()
    out: dict[int, list[float]] = {}
    for r in rows:
        out.setdefault(r["student_fk"], []).append(float(r["score_pct"]))
    return out


def create(student_fk: int, assessment_type: str, title: str, score_pct: float, recorded_on: str) -> int:
    db = get_db()
    cur = db.execute(
        "INSERT INTO assessments(student_fk, assessment_type, title, score_pct, recorded_on) "
        "VALUES (?, ?, ?, ?, ?)",
        (student_fk, assessment_type, title.strip(), score_pct, recorded_on),
    )
    db.commit()
    return cur.lastrowid


def delete(pk: int, student_fk: int):
    db = get_db()
    db.execute("DELETE FROM assessments WHERE id = ? AND student_fk = ?", (pk, student_fk))
    db.commit()
