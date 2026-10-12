import re


def test_setup_only_when_no_users(client, app):
    # Users exist (fixture), so setup must redirect away.
    assert client.get("/setup").status_code == 302
    with app.app_context():
        from app.db import get_db
        get_db().execute("DELETE FROM users")
        get_db().commit()
    r = client.get("/login")
    assert b"Create the first administrator" in r.data
    r = client.post("/setup", data={"username": "root", "full_name": "Root Admin",
                                    "password": "Root@12345", "confirm": "Root@12345"})
    assert r.status_code == 302
    assert client.get("/setup").status_code == 302  # closed again


def test_login_success_and_failure(client, auth):
    r = auth.login("admin", "wrong-password")
    assert r.status_code == 200 and b"Invalid username or password" in r.data
    r = auth.as_admin()
    assert r.status_code == 302 and r.headers["Location"].endswith("/admin/")
    assert client.get("/admin/").status_code == 200
    auth.logout()
    assert client.get("/admin/").status_code == 302  # back to login


def test_passwords_are_hashed(app):
    with app.app_context():
        from app.models import users
        row = users.get_by_username("admin")
        assert row["password_hash"] != "Admin@12345"
        assert row["password_hash"].startswith(("scrypt:", "pbkdf2:"))


def test_role_permissions(client, auth, student_login):
    # Faculty: allowed on faculty pages, forbidden on admin pages.
    auth.as_faculty()
    assert client.get("/dashboard").status_code == 200
    assert client.get("/students/").status_code == 200
    assert client.get("/admin/").status_code == 403
    assert client.get("/admin/users").status_code == 403
    assert client.post("/admin/settings", data={}).status_code == 403
    auth.logout()
    # Student: own portal only.
    auth.login(*student_login)
    assert client.get("/me/").status_code == 200
    for url in ("/dashboard", "/students/", "/predictions/", "/alerts/", "/interventions/", "/model/", "/admin/"):
        assert client.get(url).status_code == 403, url
    assert client.post("/predictions/run", data={"scope": "all"}).status_code == 403


def test_forced_password_change(client, app, auth):
    with app.app_context():
        from app.models import users
        users.create("temp", "Temp@12345", "Temp User", "faculty", must_change_password=True)
    auth.login("temp", "Temp@12345")
    r = client.get("/dashboard")
    assert r.status_code == 302 and "/change-password" in r.headers["Location"]
    r = client.post("/change-password", data={"current_password": "Temp@12345",
                                              "new_password": "Fresh@12345", "confirm": "Fresh@12345"})
    assert r.status_code == 302
    assert client.get("/dashboard").status_code == 200


def test_open_redirect_is_blocked(client, auth):
    r = client.post("/login?next=https://evil.example", data={"username": "admin", "password": "Admin@12345"})
    assert r.status_code == 302
    assert "evil.example" not in r.headers["Location"]


def test_csrf_enforced_when_enabled(tmp_path):
    from app import create_app
    from config import TestConfig
    inst = tmp_path / "i"
    app = create_app(TestConfig, {"INSTANCE_PATH": inst, "DATABASE": inst / "t.db", "MODEL_DIR": inst / "m",
                                  "UPLOAD_DIR": inst / "u", "LOG_DIR": inst / "l", "WTF_CSRF_ENABLED": True})
    c = app.test_client()
    r = c.post("/setup", data={"username": "root", "full_name": "Root", "password": "Root@12345", "confirm": "Root@12345"})
    assert r.status_code == 400  # missing token
    page = c.get("/setup").data.decode()
    token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
    r = c.post("/setup", data={"csrf_token": token, "username": "root", "full_name": "Root",
                               "password": "Root@12345", "confirm": "Root@12345"})
    assert r.status_code == 302
