"""Application settings stored in the database (editable by admins)."""
from app.db import get_db

DEFAULTS = {
    # Reference levels used for descriptive observations (NOT model rules).
    "attendance_reference": "75",
    "assignment_reference": "70",
    "score_reference": "50",
    "study_hours_reference": "2",
    # Whether students can see their own predicted risk category.
    "show_risk_to_students": "1",
    "institution_name": "MIT School of Computing, MIT-ADT University",
}


def ensure_defaults(conn=None):
    conn = conn or get_db()
    for key, value in DEFAULTS.items():
        conn.execute("INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)", (key, value))
    conn.commit()


def get_all() -> dict:
    rows = get_db().execute("SELECT key, value FROM settings").fetchall()
    data = dict(DEFAULTS)
    data.update({r["key"]: r["value"] for r in rows})
    return data


def get(key: str, default=None):
    row = get_db().execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    if row is None:
        return DEFAULTS.get(key, default)
    return row["value"]


def get_float(key: str) -> float:
    return float(get(key))


def get_bool(key: str) -> bool:
    return str(get(key)) in ("1", "true", "True", "yes")


def set_many(values: dict):
    db = get_db()
    for key, value in values.items():
        db.execute(
            "INSERT INTO settings(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )
    db.commit()
