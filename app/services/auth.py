"""Authentication helpers and role-based authorisation decorators."""
from functools import wraps

from flask import abort, flash, g, redirect, request, session, url_for

from app.models import users as users_repo


def load_current_user():
    """Populate ``g.user`` from the session (called before each request)."""
    g.user = None
    user_id = session.get("user_id")
    if user_id is not None:
        user = users_repo.get_by_id(user_id)
        if user is not None and user["is_active"]:
            g.user = user
        else:
            session.clear()


def login_user(user_row):
    session.clear()
    session["user_id"] = user_row["id"]
    session.permanent = True
    users_repo.touch_login(user_row["id"])


def logout_user():
    session.clear()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.get("user") is None:
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        if g.user["must_change_password"] and request.endpoint not in (
            "auth.change_password", "auth.logout", "static"
        ):
            flash("You must change your password before continuing.", "warning")
            return redirect(url_for("auth.change_password"))
        return view(*args, **kwargs)

    return wrapped


def roles_required(*roles):
    """Allow access only to users whose role is in ``roles`` (checked server-side)."""

    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if g.user["role"] not in roles:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


def home_url_for(user_row) -> str:
    return {
        "admin": url_for("admin.dashboard"),
        "faculty": url_for("dashboard.index"),
        "student": url_for("portal.index"),
    }.get(user_row["role"], url_for("auth.login"))


def validate_password_strength(password: str) -> list[str]:
    errors = []
    if len(password or "") < 8:
        errors.append("Password must be at least 8 characters long.")
    if password and password.isalpha():
        errors.append("Password must contain at least one digit or symbol.")
    return errors
