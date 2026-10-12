"""TrackWell Flask application factory."""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask, g, render_template, request
from flask_wtf.csrf import CSRFError, CSRFProtect

from config import Config

csrf = CSRFProtect()

APP_VERSION = "1.0.0"


def create_app(config_object=Config, overrides: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(config_object)
    if overrides:
        app.config.update(overrides)
    for key in ("INSTANCE_PATH", "DATABASE", "MODEL_DIR", "UPLOAD_DIR", "LOG_DIR", "TRAINING_DATA"):
        app.config[key] = Path(app.config[key])
    for key in ("INSTANCE_PATH", "MODEL_DIR", "UPLOAD_DIR", "LOG_DIR"):
        app.config[key].mkdir(parents=True, exist_ok=True)
    app.config["SECRET_KEY"] = app.config.get("SECRET_KEY") or _secret_key(app)
    app.config["APP_VERSION"] = APP_VERSION

    _configure_logging(app)
    csrf.init_app(app)

    from app import db
    db.init_app(app)

    from app.routes import register_blueprints
    register_blueprints(app)

    from app.services.auth import load_current_user
    app.before_request(load_current_user)

    _register_template_helpers(app)
    _register_error_handlers(app)
    app.logger.info("TrackWell %s started (database: %s)", APP_VERSION, app.config["DATABASE"])
    return app


def _secret_key(app):
    if app.config.get("TESTING"):
        return "test-secret-key-not-for-production"
    from config import _load_or_create_secret_key
    return _load_or_create_secret_key(app.config["INSTANCE_PATH"])


def _configure_logging(app):
    log_dir = app.config["LOG_DIR"]
    level = logging.DEBUG if app.config.get("DEBUG") else logging.INFO
    fmt = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    handler = RotatingFileHandler(log_dir / "trackwell.log", maxBytes=1_000_000, backupCount=3,
                                  encoding="utf-8")
    handler.setFormatter(fmt)
    handler.setLevel(level)
    for name in ("trackwell", app.logger.name):
        logger = logging.getLogger(name) if name != app.logger.name else app.logger
        if not any(isinstance(h, RotatingFileHandler) for h in logger.handlers):
            logger.addHandler(handler)
        logger.setLevel(level)


def _register_template_helpers(app):
    from app.models import alerts as alerts_repo

    @app.context_processor
    def inject_globals():
        new_alerts = 0
        if g.get("user") is not None and g.user["role"] in ("admin", "faculty"):
            try:
                new_alerts = alerts_repo.count_new()
            except Exception:  # pragma: no cover - never break page rendering for a badge
                new_alerts = 0
        return {"current_user": g.get("user"), "new_alert_count": new_alerts,
                "app_version": APP_VERSION}

    @app.template_filter("pct")
    def fmt_pct(value, digits=1):
        if value is None:
            return "—"
        return f"{float(value):.{digits}f}%"

    @app.template_filter("num")
    def fmt_num(value, digits=1):
        if value is None:
            return "—"
        return f"{float(value):.{digits}f}"

    @app.template_filter("dash")
    def fmt_dash(value):
        return "—" if value in (None, "") else value

    @app.template_filter("risk_class")
    def risk_class(level):
        return {"High": "risk-high", "Medium": "risk-medium", "Low": "risk-low"}.get(level, "risk-none")

    @app.template_filter("dt")
    def fmt_dt(value):
        if not value:
            return "—"
        return str(value)[:16]


def _register_error_handlers(app):
    @app.errorhandler(403)
    def forbidden(_e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(413)
    def too_large(_e):
        return render_template("errors/413.html"), 413

    @app.errorhandler(CSRFError)
    def csrf_error(e):
        app.logger.warning("CSRF failure on %s: %s", request.path, e.description)
        return render_template("errors/csrf.html", reason=e.description), 400

    @app.errorhandler(500)
    def server_error(e):
        app.logger.exception("Unhandled error on %s", request.path)
        return render_template("errors/500.html"), 500
