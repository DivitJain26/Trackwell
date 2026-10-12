import io
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402
from config import TestConfig  # noqa: E402

STUDENT = {
    "student_id": "CSE22001", "name": "Test Student", "class_name": "TY CSE A", "semester": "5",
    "attendance_pct": "58", "previous_gpa": "5.8", "quiz_score": "41", "test_score": "38",
    "assignment_completion_pct": "45", "study_hours": "1", "participation": "Low",
    "engagement_level": "Low", "self_understanding": "2",
}
GOOD_STUDENT = {
    "student_id": "CSE22002", "name": "Strong Student", "class_name": "TY CSE A", "semester": "5",
    "attendance_pct": "94", "previous_gpa": "8.9", "quiz_score": "85", "test_score": "82",
    "assignment_completion_pct": "98", "study_hours": "3.5", "participation": "High",
    "engagement_level": "High", "self_understanding": "5",
}


@pytest.fixture
def app(tmp_path):
    inst = tmp_path / "instance"
    application = create_app(TestConfig, {
        "INSTANCE_PATH": inst, "DATABASE": inst / "test.db", "MODEL_DIR": inst / "models",
        "UPLOAD_DIR": inst / "uploads", "LOG_DIR": inst / "logs",
        "TRAINING_DATA": ROOT / "data" / "training_data.csv",
    })
    with application.app_context():
        from app.models import users
        users.create("admin", "Admin@12345", "Site Admin", "admin")
        users.create("faculty", "Faculty@123", "Prof. Faculty", "faculty")
    yield application


@pytest.fixture
def client(app):
    return app.test_client()


class Auth:
    def __init__(self, client):
        self.client = client

    def login(self, username, password):
        return self.client.post("/login", data={"username": username, "password": password})

    def logout(self):
        return self.client.post("/logout")

    def as_admin(self):
        return self.login("admin", "Admin@12345")

    def as_faculty(self):
        return self.login("faculty", "Faculty@123")


@pytest.fixture
def auth(client):
    return Auth(client)


@pytest.fixture
def student_pk(app):
    """A seeded at-risk student; returns its primary key."""
    with app.app_context():
        from app.models import students
        from app.services.validation import validate_student_record
        clean, errors = validate_student_record(STUDENT)
        assert not errors
        return students.create(clean)


@pytest.fixture
def student_login(app, student_pk):
    with app.app_context():
        from app.models import users
        users.create("stud", "Student@123", "Test Student", "student", student_fk=student_pk)
    return ("stud", "Student@123")


@pytest.fixture
def trained_model(app):
    """Train a quick model so prediction routes work. Returns the training report."""
    with app.app_context():
        from app.services.model_service import train_new_version
        return train_new_version(None, quick=True, notes="test")


def csv_upload(client, text: str, filename="upload.csv"):
    return client.post("/import/preview", data={"file": (io.BytesIO(text.encode()), filename)},
                       content_type="multipart/form-data")
