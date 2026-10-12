"""Copy the SQLite database to instance/backups/trackwell_<timestamp>.db using the online backup API."""
import sqlite3
from datetime import datetime

from _bootstrap import make_app

if __name__ == "__main__":
    app = make_app()
    src = app.config["DATABASE"]
    dest_dir = app.config["INSTANCE_PATH"] / "backups"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"trackwell_{datetime.now():%Y%m%d_%H%M%S}.db"
    with sqlite3.connect(str(src)) as source, sqlite3.connect(str(dest)) as target:
        source.backup(target)
    print(f"Backup written to {dest}")
