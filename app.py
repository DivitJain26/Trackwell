"""Entry point: ``python app.py`` starts the local development server."""
import sys

MIN_PYTHON = (3, 10)
if sys.version_info < MIN_PYTHON:
    sys.exit(f"TrackWell requires Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer "
             f"(found {sys.version.split()[0]}).")

try:
    from app import create_app
except ModuleNotFoundError as exc:  # pragma: no cover - startup diagnostics
    sys.exit(
        f"A required package is missing: {exc.name}.\n"
        "Activate the virtual environment and run: pip install -r requirements.txt"
    )

from config import Config  # noqa: E402

try:
    app = create_app()
except Exception as exc:  # pragma: no cover - startup diagnostics
    sys.exit(f"TrackWell failed to initialise: {exc}\n"
             "Check that the 'instance' folder is writable and the database is not corrupted.")

if __name__ == "__main__":
    print(f"TrackWell is running at http://{Config.HOST}:{Config.PORT}  (press Ctrl+C to stop)")
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)
