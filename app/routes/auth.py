from flask import Blueprint, flash, g, redirect, render_template, request, url_for
from werkzeug.security import check_password_hash

from app.models import audit, users as users_repo
from app.services.auth import (home_url_for, login_required, login_user, logout_user,
                               validate_password_strength)

bp = Blueprint("auth", __name__)


def _safe_next(target: str | None):
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return None


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.get("user") is not None:
        return redirect(home_url_for(g.user))
    needs_setup = users_repo.count_admins() == 0
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = users_repo.get_by_username(username) if username else None
        if user is None or not user["is_active"] or not users_repo.verify_password(user, password):
            audit.log(None, "login_failed", "user", username[:50] or None)
            flash("Invalid username or password.", "danger")
        else:
            login_user(user)
            audit.log(user["id"], "login", "user", user["id"])
            if user["must_change_password"]:
                flash("Please set a new password before continuing.", "warning")
                return redirect(url_for("auth.change_password"))
            return redirect(_safe_next(request.args.get("next")) or home_url_for(user))
    return render_template("auth/login.html", needs_setup=needs_setup)


@bp.route("/logout", methods=["POST"])
def logout():
    if g.get("user") is not None:
        audit.log(g.user["id"], "logout", "user", g.user["id"])
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/setup", methods=["GET", "POST"])
def setup():
    """First-run administrator creation. Only available while no administrator account exists."""
    if users_repo.count_admins() > 0:
        flash("Initial setup has already been completed.", "info")
        return redirect(url_for("auth.login"))
    errors = []
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        full_name = request.form.get("full_name", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        if len(username) < 3:
            errors.append("Username must be at least 3 characters.")
        if len(full_name) < 2:
            errors.append("Full name is required.")
        errors += validate_password_strength(password)
        if password != confirm:
            errors.append("Passwords do not match.")
        if not errors:
            uid = users_repo.create(username, password, full_name, "admin")
            audit.log(uid, "initial_admin_created", "user", uid)
            flash("Administrator account created. Please sign in.", "success")
            return redirect(url_for("auth.login"))
    return render_template("auth/setup.html", errors=errors, form=request.form)


@bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    errors = []
    if request.method == "POST":
        current = request.form.get("current_password", "")
        new = request.form.get("new_password", "")
        confirm = request.form.get("confirm", "")
        if not check_password_hash(g.user["password_hash"], current):
            errors.append("Current password is incorrect.")
        errors += validate_password_strength(new)
        if new != confirm:
            errors.append("New passwords do not match.")
        if new == current:
            errors.append("New password must differ from the current password.")
        if not errors:
            users_repo.set_password(g.user["id"], new, must_change=False)
            audit.log(g.user["id"], "password_changed", "user", g.user["id"])
            flash("Password updated.", "success")
            return redirect(home_url_for(users_repo.get_by_id(g.user["id"])))
    return render_template("auth/change_password.html", errors=errors,
                           forced=bool(g.user["must_change_password"]))
