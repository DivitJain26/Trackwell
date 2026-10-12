"""Application configuration for TrackWell.

Values are read from environment variables (optionally loaded from a local
``.env`` file). Nothing secret is stored in this file.
"""
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _load_or_create_secret_key(instance_path: Path) -> str:
    """Return SECRET_KEY from the environment, or a persisted random key.

    A random key is generated once and stored in ``instance/secret_key`` so
    that sessions survive application restarts without hardcoding a secret in
    source control.
    """
    env_key = os.environ.get("TRACKWELL_SECRET_KEY")
    if env_key:
        return env_key
    key_file = instance_path / "secret_key"
    if key_file.exists():
        return key_file.read_text(encoding="utf-8").strip()
    instance_path.mkdir(parents=True, exist_ok=True)
    key = secrets.token_hex(32)
    key_file.write_text(key, encoding="utf-8")
    try:
        os.chmod(key_file, 0o600)
    except OSError:  # Windows does not support POSIX permissions
        pass
    return key


class Config:
    """Default (development) configuration."""

    INSTANCE_PATH = Path(os.environ.get("TRACKWELL_INSTANCE_PATH", BASE_DIR / "instance"))
    DATABASE = Path(os.environ.get("TRACKWELL_DATABASE", INSTANCE_PATH / "trackwell.db"))
    MODEL_DIR = Path(os.environ.get("TRACKWELL_MODEL_DIR", INSTANCE_PATH / "models"))
    UPLOAD_DIR = Path(os.environ.get("TRACKWELL_UPLOAD_DIR", INSTANCE_PATH / "uploads"))
    LOG_DIR = Path(os.environ.get("TRACKWELL_LOG_DIR", INSTANCE_PATH / "logs"))
    TRAINING_DATA = Path(os.environ.get("TRACKWELL_TRAINING_DATA", BASE_DIR / "data" / "training_data.csv"))

    DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"
    TESTING = False

    # Security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Only enable Secure cookies when served over HTTPS (not the default local setup).
    SESSION_COOKIE_SECURE = os.environ.get("TRACKWELL_HTTPS", "0") == "1"
    PERMANENT_SESSION_LIFETIME = int(os.environ.get("TRACKWELL_SESSION_MINUTES", "480")) * 60
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB upload limit
    ALLOWED_UPLOAD_EXTENSIONS = {"csv"}

    HOST = os.environ.get("TRACKWELL_HOST", "127.0.0.1")
    PORT = int(os.environ.get("TRACKWELL_PORT", "5000"))

    @classmethod
    def secret_key(cls) -> str:
        return _load_or_create_secret_key(cls.INSTANCE_PATH)


class TestConfig(Config):
    """Configuration used by the automated test-suite."""

    TESTING = True
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False
