"""User accounts and roles."""
from werkzeug.security import check_password_hash, generate_password_hash

from app.db import get_db

ROLES = ("admin", "faculty", "student")


def count() -> int:
    return get_db().execute("SELECT COUNT(*) FROM users").fetchone()[0]


def get_by_id(user_id: int):
    return get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def get_by_username(username: str):
    return get_db().execute("SELECT * FROM users WHERE username = ?", (username.strip(),)).fetchone()


def get_by_student_fk(student_fk: int):
    return get_db().execute("SELECT * FROM users WHERE student_fk = ?", (student_fk,)).fetchone()


def list_all():
    return get_db().execute(
        "SELECT u.*, s.student_id AS linked_student_id, s.name AS linked_student_name "
        "FROM users u LEFT JOIN students s ON s.id = u.student_fk "
        "ORDER BY u.role, u.username"
    ).fetchall()


def create(username: str, password: str, full_name: str, role: str,
           student_fk: int | None = None, must_change_password: bool = False) -> int:
    if role not in ROLES:
        raise ValueError(f"Unknown role: {role}")
    db = get_db()
    cur = db.execute(
        "INSERT INTO users(username, password_hash, full_name, role, student_fk, must_change_password) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (username.strip(), generate_password_hash(password), full_name.strip(), role,
         student_fk, 1 if must_change_password else 0),
    )
    db.commit()
    return cur.lastrowid


def update(user_id: int, full_name: str, role: str, is_active: bool, student_fk: int | None):
    db = get_db()
    db.execute(
        "UPDATE users SET full_name = ?, role = ?, is_active = ?, student_fk = ? WHERE id = ?",
        (full_name.strip(), role, 1 if is_active else 0, student_fk, user_id),
    )
    db.commit()


def set_password(user_id: int, password: str, must_change: bool = False):
    db = get_db()
    db.execute(
        "UPDATE users SET password_hash = ?, must_change_password = ? WHERE id = ?",
        (generate_password_hash(password), 1 if must_change else 0, user_id),
    )
    db.commit()


def verify_password(user_row, password: str) -> bool:
    return bool(user_row) and check_password_hash(user_row["password_hash"], password)


def touch_login(user_id: int):
    db = get_db()
    db.execute("UPDATE users SET last_login_at = datetime('now') WHERE id = ?", (user_id,))
    db.commit()


def delete(user_id: int):
    db = get_db()
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.commit()


def count_active_admins() -> int:
    return get_db().execute(
        "SELECT COUNT(*) FROM users WHERE role = 'admin' AND is_active = 1"
    ).fetchone()[0]


def count_admins() -> int:
    """Number of administrator accounts (active or not); used to gate first-run setup."""
    return get_db().execute("SELECT COUNT(*) FROM users WHERE role = 'admin'").fetchone()[0]
