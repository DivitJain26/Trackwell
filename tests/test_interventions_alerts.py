from datetime import date


def test_intervention_create_and_retrieve(client, auth, app, student_pk):
    auth.as_faculty()
    data = {"intervention_date": date.today().isoformat(), "intervention_type": "Mentoring",
            "notes": "Weekly mentoring agreed", "follow_up_date": date.today().isoformat(),
            "status": "Planned", "faculty_user_fk": "2"}
    r = client.post(f"/interventions/new?student={student_pk}", data=data)
    assert r.status_code == 302
    with app.app_context():
        from app.models import interventions
        rows = interventions.list_for_student(student_pk)
        assert len(rows) == 1 and rows[0]["intervention_type"] == "Mentoring"
        assert rows[0]["faculty_name"] == "Prof. Faculty"
        pk = rows[0]["id"]
    r = client.get(f"/students/{student_pk}")
    assert b"Weekly mentoring agreed" in r.data
    # status filter
    assert b"Mentoring" in client.get("/interventions/?status=Planned").data
    assert b"No interventions" in client.get("/interventions/?status=Completed").data
    # edit to completed with outcome
    data.update(status="Completed", follow_up_outcome="Attendance improved")
    assert client.post(f"/interventions/{pk}/edit", data=data).status_code == 302
    assert b"Attendance improved" in client.get("/interventions/?status=Completed").data


def test_intervention_validation(client, auth, student_pk):
    auth.as_faculty()
    r = client.post(f"/interventions/new?student={student_pk}", data={
        "intervention_date": "2026-10-10", "intervention_type": "Magic", "follow_up_date": "2026-10-01",
        "status": "Planned", "faculty_user_fk": "2"})
    assert r.status_code == 200
    assert b"valid intervention type" in r.data and b"cannot be before" in r.data


def test_student_portal_hides_faculty_notes(client, auth, app, student_pk, student_login):
    auth.as_faculty()
    client.post(f"/interventions/new?student={student_pk}", data={
        "intervention_date": "2026-10-10", "intervention_type": "Counseling Referral",
        "notes": "CONFIDENTIAL faculty note", "status": "Planned", "faculty_user_fk": "2"})
    auth.logout()
    auth.login(*student_login)
    r = client.get("/me/")
    assert r.status_code == 200
    assert b"Counseling Referral" in r.data and b"CONFIDENTIAL" not in r.data


def test_alerts_created_once_and_reviewable(client, auth, app, student_pk, trained_model):
    auth.as_faculty()
    client.post("/predictions/run", data={"scope": "all"})
    with app.app_context():
        from app.models import alerts
        first = alerts.list_alerts()
        assert len(first) == 1 and first[0]["alert_type"] == "new_high_risk" and first[0]["status"] == "new"
    # Re-running with unchanged results must not duplicate the alert.
    client.post("/predictions/run", data={"scope": "all"})
    with app.app_context():
        from app.models import alerts
        assert len(alerts.list_alerts()) == 1
        aid = alerts.list_alerts()[0]["id"]
    r = client.post(f"/alerts/{aid}/review", data={"then": "intervene"})
    assert r.status_code == 302 and "/interventions/new" in r.headers["Location"]
    with app.app_context():
        from app.models import alerts
        a = alerts.get_by_id(aid)
        assert a["status"] == "reviewed" and a["reviewed_by_fk"] == 2
    # Linking: creating the intervention from the alert sets intervention_fk.
    client.post(f"/interventions/new?student={student_pk}&alert={aid}", data={
        "intervention_date": "2026-10-12", "intervention_type": "Attendance Follow-up",
        "status": "Planned", "faculty_user_fk": "2"})
    with app.app_context():
        from app.models import alerts
        assert alerts.get_by_id(aid)["intervention_fk"] is not None
