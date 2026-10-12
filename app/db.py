"""SQLite database helpers.

A single connection is opened per request (stored on ``flask.g``) and closed
when the request ends. All queries use parameter binding; SQL is never built
from untrusted input.
"""
import sqlite3
from pathlib import Path

from flask import current_app, g

SCHEMA_VERSION = 1


def get_db() -> sqlite3.Connection:
    """Return the request-scoped database connection."""
    if "db" not in g:
        db_path = Path(current_app.config["DATABASE"])
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path), detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        g.db = conn
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def _apply_schema(conn: sqlite3.Connection):
    schema_path = Path(__file__).with_name("schema.sql")
    conn.executescript(schema_path.read_text(encoding="utf-8"))


# Incremental migrations keyed by target version. Version 1 is the base schema.
# Add new entries here (never edit existing ones) when the schema changes.
MIGRATIONS = {
    # 2: ["ALTER TABLE students ADD COLUMN email TEXT"],
}


def init_db(conn: sqlite3.Connection | None = None):
    """Create tables if they do not exist and apply pending migrations.

    Existing data is preserved: the schema uses ``CREATE TABLE IF NOT EXISTS``
    and migrations are only applied once.
    """
    own = conn is None
    if own:
        conn = get_db()
    _apply_schema(conn)
    applied = {r["version"] for r in conn.execute("SELECT version FROM schema_migrations")}
    if 1 not in applied:
        conn.execute("INSERT INTO schema_migrations(version) VALUES (1)")
    for version in sorted(MIGRATIONS):
        if version in applied:
            continue
        for stmt in MIGRATIONS[version]:
            conn.execute(stmt)
        conn.execute("INSERT INTO schema_migrations(version) VALUES (?)", (version,))
    conn.commit()
    from app.models import settings as settings_repo  # local import avoids cycles

    settings_repo.ensure_defaults(conn)


def init_app(app):
    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()
