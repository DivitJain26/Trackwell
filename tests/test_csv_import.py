import re

from tests.conftest import csv_upload

HEADER = ("student_id,name,class_name,semester,attendance_pct,previous_gpa,quiz_score,test_score,"
          "assignment_completion_pct,study_hours,participation,engagement_level,self_understanding\n")


def _token(data: bytes) -> str:
    return re.search(rb'name="token" value="([^"]+)"', data).group(1).decode()


def test_template_download(client, auth):
    auth.as_faculty()
    r = client.get("/import/template.csv")
    assert r.status_code == 200 and r.data.startswith(b"student_id,name,class_name")


def test_validation_report_and_import(client, auth, app):
    auth.as_faculty()
    text = HEADER + (
        "CSE22010,Valid One,TY CSE A,5,82,7.5,70,65,90,2.5,Medium,High,4\n"
        "CSE22011,Bad Attendance,TY CSE A,5,130,7.5,70,65,90,2.5,Medium,High,4\n"
        "CSE22012,Bad Level,TY CSE A,5,80,7.5,70,65,90,2.5,Often,High,4\n"
        "CSE22010,Duplicate In File,TY CSE A,5,80,7.5,70,65,90,2.5,Low,Low,3\n"
        "CSE22013,Missing Required,,5,80,,,,90,,Low,Low,\n"
        "CSE22014,Blank Optionals,TY CSE B,5,80,,,,90,,Low,Low,\n"
    )
    r = csv_upload(client, text)
    assert r.status_code == 200
    assert b"Attendance % must be between 0 and 100" in r.data
    assert b"participation must be one of Low, Medium or High" in r.data
    assert b"Duplicate student_id in file" in r.data
    assert b"class_name is required" in r.data
    token = _token(r.data)
    # Confirm without acknowledging invalid rows is refused.
    r = client.post("/import/confirm", data={"token": token, "on_existing": "skip"})
    assert r.status_code == 200 and b"confirm that invalid rows should be skipped" in r.data
    r = client.post("/import/confirm", data={"token": token, "on_existing": "skip", "acknowledge_invalid": "1"})
    assert r.status_code == 302
    with app.app_context():
        from app.models import students
        ids = {s["student_id"] for s in students.list_all()}
        assert ids == {"CSE22010", "CSE22014"}
        assert students.get_by_student_id("CSE22014")["previous_gpa"] is None


def test_missing_columns_block_import(client, auth, app):
    auth.as_faculty()
    r = csv_upload(client, "student_id,name\nX1,Someone\n")
    assert r.status_code == 200 and b"Missing required columns" in r.data
    assert b'name="on_existing"' not in r.data  # confirm form not offered
    with app.app_context():
        from app.models import students
        assert students.count() == 0


def test_existing_rows_skip_or_update(client, auth, app, student_pk):
    auth.as_faculty()
    text = HEADER + "CSE22001,Updated Name,TY CSE A,5,70,6,50,50,60,2,Medium,Medium,3\n"
    r = csv_upload(client, text)
    assert b"Exists" in r.data
    client.post("/import/confirm", data={"token": _token(r.data), "on_existing": "skip"})
    with app.app_context():
        from app.models import students
        assert students.get_by_id(student_pk)["name"] == "Test Student"
    r = csv_upload(client, text)
    client.post("/import/confirm", data={"token": _token(r.data), "on_existing": "update"})
    with app.app_context():
        from app.models import students
        row = students.get_by_id(student_pk)
        assert row["name"] == "Updated Name" and row["attendance_pct"] == 70.0
        assert students.count() == 1


def test_rejects_non_csv_and_empty(client, auth):
    auth.as_faculty()
    r = csv_upload(client, "whatever", filename="data.xlsx")
    assert r.status_code == 302
    r = client.get("/import/")
    assert b"Only .csv files are accepted" in r.data
    r = csv_upload(client, "")
    assert r.status_code == 302


def test_stale_token_rejected(client, auth):
    auth.as_faculty()
    r = client.post("/import/confirm", data={"token": "not-a-real-token", "on_existing": "skip"})
    assert r.status_code == 302
