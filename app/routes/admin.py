from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from app.models import audit, settings as settings_repo, students as students_repo, users as users_repo
from app.services.auth import roles_required, validate_password_strength
from app.services.dashboard_service import admin_summary

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/")
@roles_required("admin")
def dashboard():
    return render_template("admin/dashboard.html", summary=admin_summary(),
                           recent_events=audit.recent(10))


@bp.route("/users")
@roles_required("admin")
def users():
    return render_template("admin/users.html", users=users_repo.list_all())


def _user_form_data():
    return {
        "username": request.form.get("username", "").strip(),
        "full_name": request.form.get("full_name", "").strip(),
        "role": request.form.get("role", "faculty"),
        "student_id": request.form.get("student_id", "").strip(),
        "is_active": request.form.get("is_active") == "1",
        "password": request.form.get("password", ""),
        "must_change_password": request.form.get("must_change_password") == "1",
    }


def _resolve_student_fk(data, errors):
    if data["role"] != "student":
        return None
    if not data["student_id"]:
        errors.append("A student account must be linked to an existing student ID.")
        return None
    student = students_repo.get_by_student_id(data["student_id"])
    if student is None:
        errors.append(f"No student record with ID '{data['student_id']}' exists.")
        return None
    return student["id"]


@bp.route("/users/new", methods=["GET", "POST"])
@roles_required("admin")
def user_new():
    errors = []
    data = _user_form_data() if request.method == "POST" else {"role": "faculty", "is_active": True,
                                                                "must_change_password": True}
    if request.method == "POST":
        if len(data["username"]) < 3:
            errors.append("Username must be at least 3 characters.")
        elif users_repo.get_by_username(data["username"]):
            errors.append("That username is already taken.")
        if len(data["full_name"]) < 2:
            errors.append("Full name is required.")
        if data["role"] not in users_repo.ROLES:
            errors.append("Invalid role.")
        errors += validate_password_strength(data["password"])
        student_fk = _resolve_student_fk(data, errors)
        if student_fk and users_repo.get_by_student_fk(student_fk):
            errors.append("That student already has a login account.")
        data["is_active"] = True
        if not errors:
            uid = users_repo.create(data["username"], data["password"], data["full_name"], data["role"],
                                    student_fk=student_fk, must_change_password=data["must_change_password"])
            audit.log(g.user["id"], "user_created", "user", uid, f"role={data['role']}")
            flash(f"User '{data['username']}' created.", "success")
            return redirect(url_for("admin.users"))
    return render_template("admin/user_form.html", errors=errors, data=data, mode="new", user=None)


@bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@roles_required("admin")
def user_edit(user_id):
    user = users_repo.get_by_id(user_id)
    if user is None:
        abort(404)
    errors = []
    if request.method == "POST":
        data = _user_form_data()
        if len(data["full_name"]) < 2:
            errors.append("Full name is required.")
        if data["role"] not in users_repo.ROLES:
            errors.append("Invalid role.")
        student_fk = _resolve_student_fk(data, errors)
        if student_fk:
            other = users_repo.get_by_student_fk(student_fk)
            if other and other["id"] != user_id:
                errors.append("That student is already linked to another account.")
        if user["role"] == "admin" and (data["role"] != "admin" or not data["is_active"]) \
                and users_repo.count_active_admins() <= 1:
            errors.append("At least one active administrator must remain.")
        if not errors:
            users_repo.update(user_id, data["full_name"], data["role"], data["is_active"], student_fk)
            audit.log(g.user["id"], "user_updated", "user", user_id)
            flash("User updated.", "success")
            return redirect(url_for("admin.users"))
    else:
        linked = students_repo.get_by_id(user["student_fk"]) if user["student_fk"] else None
        data = {"username": user["username"], "full_name": user["full_name"], "role": user["role"],
                "student_id": linked["student_id"] if linked else "", "is_active": bool(user["is_active"]),
                "must_change_password": bool(user["must_change_password"])}
    return render_template("admin/user_form.html", errors=errors, data=data, mode="edit", user=user)


@bp.route("/users/<int:user_id>/reset-password", methods=["POST"])
@roles_required("admin")
def user_reset_password(user_id):
    user = users_repo.get_by_id(user_id)
    if user is None:
        abort(404)
    password = request.form.get("password", "")
    errors = validate_password_strength(password)
    if errors:
        for e in errors:
            flash(e, "danger")
    else:
        users_repo.set_password(user_id, password, must_change=True)
        audit.log(g.user["id"], "password_reset", "user", user_id)
        flash(f"Temporary password set for '{user['username']}'. They must change it at next login.", "success")
    return redirect(url_for("admin.users"))


@bp.route("/users/<int:user_id>/delete", methods=["POST"])
@roles_required("admin")
def user_delete(user_id):
    user = users_repo.get_by_id(user_id)
    if user is None:
        abort(404)
    if user["id"] == g.user["id"]:
        flash("You cannot delete your own account.", "danger")
    elif user["role"] == "admin" and users_repo.count_active_admins() <= 1:
        flash("At least one administrator must remain.", "danger")
    else:
        users_repo.delete(user_id)
        audit.log(g.user["id"], "user_deleted", "user", user_id, user["username"])
        flash(f"User '{user['username']}' deleted.", "success")
    return redirect(url_for("admin.users"))


@bp.route("/settings", methods=["GET", "POST"])
@roles_required("admin")
def settings():
    errors = []
    if request.method == "POST":
        values = {}
        for key, label, lo, hi in (
            ("attendance_reference", "Attendance reference", 0, 100),
            ("assignment_reference", "Assignment reference", 0, 100),
            ("score_reference", "Score reference", 0, 100),
            ("study_hours_reference", "Study hours reference", 0, 16),
        ):
            try:
                v = float(request.form.get(key, ""))
                if not lo <= v <= hi:
                    raise ValueError
                values[key] = f"{v:g}"
            except ValueError:
                errors.append(f"{label} must be a number between {lo} and {hi}.")
        values["show_risk_to_students"] = "1" if request.form.get("show_risk_to_students") == "1" else "0"
        values["institution_name"] = request.form.get("institution_name", "").strip()[:120] or \
            settings_repo.DEFAULTS["institution_name"]
        if not errors:
            settings_repo.set_many(values)
            audit.log(g.user["id"], "settings_updated", "settings", None)
            flash("Settings saved.", "success")
            return redirect(url_for("admin.settings"))
    return render_template("admin/settings.html", settings=settings_repo.get_all(), errors=errors)


@bp.route("/audit")
@roles_required("admin")
def audit_log():
    return render_template("admin/audit.html", events=audit.recent(200))
