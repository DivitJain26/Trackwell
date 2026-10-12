from tests.conftest import GOOD_STUDENT, STUDENT


def test_dashboard_empty_state(client, auth):
    auth.as_faculty()
    r = client.get("/dashboard")
    assert r.status_code == 200
    assert b"No students registered" in r.data and b"No predictions yet" in r.data


def test_dashboard_aggregation_matches_database(client, auth, app, trained_model):
    with app.app_context():
        from app.models import students
        from app.services.validation import validate_student_record
        for rec in (STUDENT, GOOD_STUDENT, dict(GOOD_STUDENT, student_id="CSE22003", class_name="TY CSE B")):
            clean, errors = validate_student_record(rec)
            assert not errors
            students.create(clean)
    auth.as_faculty()
    client.post("/predictions/run", data={"scope": "all"})
    with app.app_context():
        from app.db import get_db
        from app.services.dashboard_service import faculty_summary
        s = faculty_summary()
        db = get_db()
        assert s["total_students"] == 3 == db.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        assert s["predicted_total"] == 3 and s["unpredicted"] == 0
        assert sum(s["risk_counts"].values()) == 3
        assert s["risk_counts"]["High"] >= 1 and s["risk_counts"]["Low"] >= 1
        expected_att = db.execute("SELECT AVG(attendance_pct) FROM students").fetchone()[0]
        assert abs(s["avg_attendance"] - expected_att) < 1e-9
        assert {r["class_name"] for r in s["by_class"]} == {"TY CSE A", "TY CSE B"}
        assert s["attendance_bands"]["low"] == 1 and s["attendance_bands"]["good"] == 2
        assert s["model"]["available"] and s["model"]["version"] == trained_model["version"]
    r = client.get("/dashboard")
    assert b"Highest-risk students" in r.data and b"CSE22001" in r.data
    assert b'"High": ' in r.data  # chart data rendered from counts
    r = client.get("/predictions/export.csv")
    assert r.data.count(b"\n") == 4  # header + 3 rows


def test_admin_dashboard_counts(client, auth, app):
    auth.as_admin()
    r = client.get("/admin/")
    assert r.status_code == 200
    with app.app_context():
        from app.services.dashboard_service import admin_summary
        s = admin_summary()
        assert s["user_total"] == 2 and s["role_counts"] == {"admin": 1, "faculty": 1, "student": 0}
