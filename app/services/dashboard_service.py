"""Aggregations for the faculty and admin dashboards (all from live DB data)."""
from app.db import get_db
from app.models import alerts as alerts_repo
from app.models import interventions as interventions_repo
from app.models import predictions as predictions_repo
from app.models import students as students_repo
from app.models import users as users_repo
from app.services.model_service import model_status


def faculty_summary() -> dict:
    stats = students_repo.summary_stats()
    counts = predictions_repo.risk_counts()
    predicted_total = sum(counts.values())
    by_class = get_db().execute(
        """
        SELECT s.class_name,
               COUNT(*) AS total,
               SUM(CASE WHEN p.risk_level = 'High' THEN 1 ELSE 0 END) AS high,
               SUM(CASE WHEN p.risk_level = 'Medium' THEN 1 ELSE 0 END) AS medium,
               SUM(CASE WHEN p.risk_level = 'Low' THEN 1 ELSE 0 END) AS low,
               ROUND(AVG(s.attendance_pct), 1) AS avg_attendance
        FROM students s
        LEFT JOIN predictions p ON p.id = (
            SELECT id FROM predictions WHERE student_fk = s.id ORDER BY created_at DESC, id DESC LIMIT 1)
        GROUP BY s.class_name ORDER BY s.class_name
        """
    ).fetchall()
    attendance_bands = get_db().execute(
        """
        SELECT SUM(CASE WHEN attendance_pct < 65 THEN 1 ELSE 0 END) AS low,
               SUM(CASE WHEN attendance_pct >= 65 AND attendance_pct < 75 THEN 1 ELSE 0 END) AS borderline,
               SUM(CASE WHEN attendance_pct >= 75 THEN 1 ELSE 0 END) AS good
        FROM students
        """
    ).fetchone()
    return {
        "total_students": stats["total"] or 0,
        "avg_attendance": stats["avg_attendance"],
        "avg_assignment": stats["avg_assignment"],
        "low_attendance_count": stats["low_attendance"] or 0,
        "risk_counts": counts,
        "predicted_total": predicted_total,
        "unpredicted": (stats["total"] or 0) - predicted_total,
        "by_class": [dict(r) for r in by_class],
        "attendance_bands": dict(attendance_bands) if attendance_bands else {},
        "new_alerts": alerts_repo.count_new(),
        "intervention_counts": interventions_repo.status_counts(),
        "overdue_followups": len(interventions_repo.list_all(overdue_only=True)),
        "last_prediction_at": predictions_repo.last_prediction_time(),
        "model": model_status(),
    }


def admin_summary() -> dict:
    users = users_repo.list_all()
    role_counts = {"admin": 0, "faculty": 0, "student": 0}
    for u in users:
        role_counts[u["role"]] += 1
    summary = faculty_summary()
    summary["role_counts"] = role_counts
    summary["user_total"] = len(users)
    summary["inactive_users"] = sum(1 for u in users if not u["is_active"])
    return summary
