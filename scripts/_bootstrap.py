"""Shared helper so scripts can import the application package from any CWD."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def make_app():
    try:
        from app import create_app
    except ModuleNotFoundError as exc:
        sys.exit(f"Missing dependency '{exc.name}'. Activate the virtual environment and run: "
                 "pip install -r requirements.txt")
    return create_app()
