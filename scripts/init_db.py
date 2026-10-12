"""Create the SQLite database/schema (safe to run repeatedly; existing data is kept)."""
from _bootstrap import make_app

if __name__ == "__main__":
    app = make_app()
    with app.app_context():
        from app.db import get_db
        tables = [r[0] for r in get_db().execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
    print(f"Database ready at {app.config['DATABASE']}")
    print(f"Tables: {', '.join(tables)}")
