"""Audit trail of significant actions (never stores passwords)."""
from app.db import get_db


def log(user_id: int | None, action: str, entity_type: str | None = None,
        entity_id=None, details: str | None = None):
    db = get_db()
    db.execute(
        "INSERT INTO audit_events(user_fk, action, entity_type, entity_id, details) VALUES (?, ?, ?, ?, ?)",
        (user_id, action, entity_type, str(entity_id) if entity_id is not None else None, details),
    )
    db.commit()


def recent(limit: int = 100):
    return get_db().execute(
        "SELECT a.*, u.username FROM audit_events a LEFT JOIN users u ON u.id = a.user_fk "
        "ORDER BY a.created_at DESC, a.id DESC LIMIT ?",
        (limit,),
    ).fetchall()
