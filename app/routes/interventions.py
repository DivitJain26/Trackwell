from datetime import date

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from app.models import alerts as alerts_repo
from app.models import audit
from app.models import interventions as repo
from app.models import students as students_repo
from app.models import users as users_repo
from app.services.auth import roles_required

bp = Blueprint("interventions", __name__, url_prefix="/interventions")


@bp.route("/")
@roles_required("faculty", "admin")
def index():
    status = request.args.get("status", "")
    overdue = request.args.get("overdue") == "1"
    rows = repo.list_all(status=status, overdue_only=overdue)
    return render_template("interventions/list.html", interventions=rows, status=status, overdue=overdue,
                           statuses=repo.STATUSES, counts=repo.status_counts(), today=date.today().isoformat())


def _faculty_choices():
    return [u for u in users_repo.list_all() if u["role"] in ("faculty", "admin") and u["is_active"]]


def _parse_form(student_fk: int):
    data = {
        "student_fk": student_fk,
        "intervention_date": request.form.get("intervention_date", "").strip(),
        "intervention_type": request.form.get("intervention_type", "").strip(),
        "notes": request.form.get("notes", "").strip() or None,
        "follow_up_date": request.form.get("follow_up_date", "").strip() or None,
        "status": request.form.get("status", "Planned"),
        "follow_up_outcome": request.form.get("follow_up_outcome", "").strip() or None,
    }
    errors = []
    try:
        date.fromisoformat(data["intervention_date"])
    except ValueError:
        errors.append("Intervention date must be a valid date.")
    if data["follow_up_date"]:
        try:
            if date.fromisoformat(data["follow_up_date"]) < date.fromisoformat(data["intervention_date"]):
                errors.append("Follow-up date cannot be before the intervention date.")
        except ValueError:
            errors.append("Follow-up date must be a valid date.")
    if data["intervention_type"] not in repo.TYPES:
        errors.append("Please choose a valid intervention type.")
    if data["status"] not in repo.STATUSES:
        errors.append("Please choose a valid status.")
    if data["notes"] and len(data["notes"]) > 2000:
        errors.append("Notes must be at most 2000 characters.")
    try:
        fac = int(request.form.get("faculty_user_fk", "") or g.user["id"])
        if not any(u["id"] == fac for u in _faculty_choices()):
            raise ValueError
        data["faculty_user_fk"] = fac
    except ValueError:
        errors.append("Please choose a valid responsible faculty member.")
    return data, errors


@bp.route("/new", methods=["GET", "POST"])
@roles_required("faculty", "admin")
def new():
    student_fk = request.values.get("student", type=int)
    alert_fk = request.values.get("alert", type=int)
    student = students_repo.get_by_id(student_fk) if student_fk else None
    if student is None:
        flash("Choose a student first to record an intervention.", "warning")
        return redirect(url_for("students.list_students"))
    errors = []
    data = {"intervention_date": date.today().isoformat(), "status": "Planned",
            "faculty_user_fk": g.user["id"], "intervention_type": "", "notes": "",
            "follow_up_date": "", "follow_up_outcome": ""}
    if request.method == "POST":
        data, errors = _parse_form(student["id"])
        if not errors:
            pk = repo.create(data)
            if alert_fk:
                alerts_repo.mark_reviewed(alert_fk, g.user["id"], intervention_fk=pk)
            audit.log(g.user["id"], "intervention_created", "intervention", pk, f"student={student['student_id']}")
            flash("Intervention recorded.", "success")
            return redirect(url_for("students.detail", pk=student["id"]) + "#interventions")
    return render_template("interventions/form.html", mode="new", data=data, errors=errors, student=student,
                           types=repo.TYPES, statuses=repo.STATUSES, faculty=_faculty_choices(), alert_fk=alert_fk)


@bp.route("/<int:pk>/edit", methods=["GET", "POST"])
@roles_required("faculty", "admin")
def edit(pk):
    row = repo.get_by_id(pk)
    if row is None:
        abort(404)
    student = students_repo.get_by_id(row["student_fk"])
    errors = []
    if request.method == "POST":
        data, errors = _parse_form(row["student_fk"])
        if not errors:
            repo.update(pk, data)
            audit.log(g.user["id"], "intervention_updated", "intervention", pk)
            flash("Intervention updated.", "success")
            return redirect(url_for("students.detail", pk=row["student_fk"]) + "#interventions")
    else:
        data = dict(row)
    return render_template("interventions/form.html", mode="edit", data=data, errors=errors, student=student,
                           types=repo.TYPES, statuses=repo.STATUSES, faculty=_faculty_choices(), alert_fk=None,
                           intervention=row)


@bp.route("/<int:pk>/delete", methods=["POST"])
@roles_required("faculty", "admin")
def delete(pk):
    row = repo.get_by_id(pk)
    if row is None:
        abort(404)
    repo.delete(pk)
    audit.log(g.user["id"], "intervention_deleted", "intervention", pk)
    flash("Intervention deleted.", "success")
    return redirect(url_for("students.detail", pk=row["student_fk"]) + "#interventions")
