from tests.conftest import GOOD_STUDENT, STUDENT


def test_student_crud(client, auth, app):
    auth.as_faculty()
    r = client.post("/students/new", data=STUDENT)
    assert r.status_code == 302
    with app.app_context():
        from app.models import students
        row = students.get_by_student_id("CSE22001")
        assert row is not None and row["name"] == "Test Student" and row["attendance_pct"] == 58.0
        pk = row["id"]
    r = client.get(f"/students/{pk}")
    assert r.status_code == 200 and b"Test Student" in r.data
    edited = dict(STUDENT, name="Renamed Student", attendance_pct="61.5")
    assert client.post(f"/students/{pk}/edit", data=edited).status_code == 302
    with app.app_context():
        from app.models import students
        assert students.get_by_id(pk)["name"] == "Renamed Student"
        assert students.get_by_id(pk)["attendance_pct"] == 61.5
    r = client.get("/students/?q=Renamed")
    assert b"Renamed Student" in r.data
    r = client.get("/students/?q=NOBODY")
    assert b"No students match" in r.data
    assert client.post(f"/students/{pk}/delete").status_code == 302
    assert client.get(f"/students/{pk}").status_code == 404


def test_duplicate_student_id_rejected(client, auth, app):
    auth.as_faculty()
    assert client.post("/students/new", data=STUDENT).status_code == 302
    r = client.post("/students/new", data=dict(STUDENT, name="Someone Else"))
    assert r.status_code == 200 and b"already exists" in r.data
    # Case-insensitive uniqueness.
    r = client.post("/students/new", data=dict(STUDENT, student_id="cse22001"))
    assert r.status_code == 200 and b"already exists" in r.data
    with app.app_context():
        from app.models import students
        assert students.count() == 1


def test_invalid_data_and_missing_values(client, auth, app):
    auth.as_faculty()
    bad = dict(STUDENT, attendance_pct="140", semester="9", participation="Sometimes", self_understanding="7")
    r = client.post("/students/new", data=bad)
    assert r.status_code == 200
    for msg in (b"Attendance % must be between 0 and 100", b"semester must be between 1 and 8",
                b"participation must be one of Low, Medium or High", b"self_understanding must be between 1 and 5"):
        assert msg in r.data
    missing = {k: ("" if k in ("name", "attendance_pct") else v) for k, v in STUDENT.items()}
    r = client.post("/students/new", data=missing)
    assert b"name is required" in r.data and b"attendance_pct is required" in r.data
    with app.app_context():
        from app.models import students
        assert students.count() == 0
    # Optional fields may be blank and are stored as NULL.
    partial = dict(STUDENT, previous_gpa="", quiz_score="", test_score="", study_hours="", self_understanding="")
    assert client.post("/students/new", data=partial).status_code == 302
    with app.app_context():
        from app.models import students
        row = students.get_by_student_id("CSE22001")
        assert row["previous_gpa"] is None and row["quiz_score"] is None


def test_unauthorized_access_to_student_records(client, auth, app, student_pk, student_login):
    # Anonymous -> redirected to login
    r = client.get(f"/students/{student_pk}")
    assert r.status_code == 302 and "/login" in r.headers["Location"]
    # Student role -> forbidden on faculty record pages, even for their own record
    auth.login(*student_login)
    assert client.get(f"/students/{student_pk}").status_code == 403
    assert client.get(f"/students/{student_pk}/edit").status_code == 403
    assert client.post(f"/students/{student_pk}/delete").status_code == 403
    assert client.get("/students/export.csv").status_code == 403
    # Another student's record is never visible through the portal.
    with app.app_context():
        from app.models import students
        from app.services.validation import validate_student_record
        clean, _ = validate_student_record(GOOD_STUDENT)
        students.create(clean)
    r = client.get("/me/")
    assert b"Test Student" in r.data and b"Strong Student" not in r.data


def test_export_csv(client, auth, student_pk):
    auth.as_faculty()
    r = client.get("/students/export.csv")
    assert r.status_code == 200 and r.mimetype == "text/csv"
    assert b"student_id,name" in r.data and b"CSE22001" in r.data


def test_data_persists_across_app_restart(tmp_path):
    from app import create_app
    from config import TestConfig
    inst = tmp_path / "persist"
    overrides = {"INSTANCE_PATH": inst, "DATABASE": inst / "t.db", "MODEL_DIR": inst / "m",
                 "UPLOAD_DIR": inst / "u", "LOG_DIR": inst / "l"}
    app1 = create_app(TestConfig, overrides)
    with app1.app_context():
        from app.models import students
        from app.services.validation import validate_student_record
        clean, _ = validate_student_record(STUDENT)
        students.create(clean)
    app2 = create_app(TestConfig, overrides)  # simulates a restart
    with app2.app_context():
        from app.models import students
        assert students.get_by_student_id("CSE22001") is not None
