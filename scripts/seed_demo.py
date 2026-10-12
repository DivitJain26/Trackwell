"""Load the SYNTHETIC demo roster and create demo-only accounts.

- Imports data/sample_students.csv (skips IDs that already exist)
- Imports data/sample_assessments.csv for score-trend features
- Creates faculty.demo / student.demo with temporary passwords that must be changed at first login

It never creates an administrator; use the setup page or scripts/create_admin.py for that.
"""
import pandas as pd

from _bootstrap import ROOT, make_app

DEMO_ACCOUNTS = [
    # username, full name, role, temporary password, linked student id
    ("faculty.demo", "Demo Faculty", "faculty", "Faculty@2026", None),
    ("student.demo", "Demo Student", "student", "Student@2026", "CSE22001"),
]


def main():
    app = make_app()
    with app.app_context():
        from app.models import assessments, audit, students, users
        from app.services.validation import validate_student_record

        df = pd.read_csv(ROOT / "data" / "sample_students.csv", dtype=str, keep_default_na=False)
        added = skipped = invalid = 0
        for rec in df.to_dict(orient="records"):
            clean, errors = validate_student_record(rec)
            if errors:
                invalid += 1
                print(f"  skipped invalid row {rec.get('student_id')}: {errors}")
                continue
            if students.get_by_student_id(clean["student_id"]):
                skipped += 1
                continue
            students.create(clean)
            added += 1
        print(f"Students: {added} added, {skipped} already existed, {invalid} invalid.")

        adf = pd.read_csv(ROOT / "data" / "sample_assessments.csv", dtype=str, keep_default_na=False)
        a_added = 0
        for rec in adf.to_dict(orient="records"):
            s = students.get_by_student_id(rec["student_id"])
            if s is None:
                continue
            existing = {(a["title"], a["recorded_on"]) for a in assessments.list_for_student(s["id"])}
            if (rec["title"], rec["recorded_on"]) in existing:
                continue
            assessments.create(s["id"], rec["assessment_type"], rec["title"], float(rec["score_pct"]),
                               rec["recorded_on"])
            a_added += 1
        print(f"Assessments: {a_added} added.")

        for username, full_name, role, password, sid in DEMO_ACCOUNTS:
            if users.get_by_username(username):
                print(f"Account {username} already exists - left unchanged.")
                continue
            student_fk = None
            if sid:
                s = students.get_by_student_id(sid)
                if s is None:
                    print(f"Student {sid} not found; {username} not created.")
                    continue
                if users.get_by_student_fk(s["id"]):
                    print(f"Student {sid} already has an account; {username} not created.")
                    continue
                student_fk = s["id"]
            uid = users.create(username, password, full_name, role, student_fk=student_fk,
                               must_change_password=True)
            audit.log(uid, "demo_account_created", "user", uid, "scripts/seed_demo.py")
            print(f"Created DEMO account {username} ({role}) - temporary password: {password} "
                  f"(must be changed at first login)")
    print("\nDemo data loaded. These records are synthetic and for demonstration only.")


if __name__ == "__main__":
    main()
