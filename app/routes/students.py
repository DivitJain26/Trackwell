from datetime import date

from flask import (Blueprint, Response, abort, flash, g, redirect, render_template, request, url_for)

from app.ml.features import compute_score_trend
from app.models import alerts as alerts_repo
from app.models import assessments as assessments_repo
from app.models import audit
from app.models import interventions as interventions_repo
from app.models import predictions as predictions_repo
from app.models import settings as settings_repo
from app.models import students as students_repo
from app.models import users as users_repo
from app.services.auth import roles_required
from app.services.csv_import import export_students_csv
from app.services.model_service import ArtifactError, model_status
from app.services.observations import build_observations
from app.services.prediction_service import ModelUnavailable, predict_for_students
from app.services.validation import validate_student_record

bp = Blueprint("students", __name__, url_prefix="/students")

FORM_FIELDS = students_repo.FIELDS


def _filters():
    return {
        "q": request.args.get("q", "").strip(),
        "class_name": request.args.get("class_name", "").strip(),
        "semester": request.args.get("semester", "").strip(),
        "risk": request.args.get("risk", "").strip(),
        "sort": request.args.get("sort", "student_id"),
    }


@bp.route("/")
@roles_required("faculty", "admin")
def list_students():
    f = _filters()
    rows = students_repo.search(f["q"], f["class_name"], f["semester"], f["risk"], f["sort"])
    return render_template("students/list.html", students=rows, filters=f,
                           classes=students_repo.distinct_classes(),
                           semesters=students_repo.distinct_semesters(),
                           total=students_repo.count())


@bp.route("/export.csv")
@roles_required("faculty", "admin")
def export_csv():
    f = _filters()
    rows = students_repo.search(f["q"], f["class_name"], f["semester"], f["risk"], f["sort"])
    audit.log(g.user["id"], "students_exported", "students", None, f"{len(rows)} rows")
    return Response(export_students_csv(rows), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=trackwell_students_{date.today()}.csv"})


def _form_raw():
    return {f: request.form.get(f, "") for f in FORM_FIELDS}


@bp.route("/new", methods=["GET", "POST"])
@roles_required("faculty", "admin")
def new():
    errors, raw = [], {f: "" for f in FORM_FIELDS}
    if request.method == "POST":
        raw = _form_raw()
        clean, errors = validate_student_record(raw)
        if not errors and students_repo.get_by_student_id(clean["student_id"]):
            errors.append(f"A student with ID '{clean['student_id']}' already exists.")
        if not errors:
            pk = students_repo.create(clean)
            audit.log(g.user["id"], "student_created", "student", pk, clean["student_id"])
            flash(f"Student {clean['student_id']} added.", "success")
            return redirect(url_for("students.detail", pk=pk))
    return render_template("students/form.html", mode="new", raw=raw, errors=errors, student=None)


@bp.route("/<int:pk>/edit", methods=["GET", "POST"])
@roles_required("faculty", "admin")
def edit(pk):
    student = students_repo.get_by_id(pk)
    if student is None:
        abort(404)
    errors = []
    if request.method == "POST":
        raw = _form_raw()
        clean, errors = validate_student_record(raw)
        if not errors:
            other = students_repo.get_by_student_id(clean["student_id"])
            if other and other["id"] != pk:
                errors.append(f"Another student already uses ID '{clean['student_id']}'.")
        if not errors:
            students_repo.update(pk, clean)
            audit.log(g.user["id"], "student_updated", "student", pk)
            flash("Student record updated.", "success")
            return redirect(url_for("students.detail", pk=pk))
    else:
        raw = {f: ("" if student[f] is None else student[f]) for f in FORM_FIELDS}
    return render_template("students/form.html", mode="edit", raw=raw, errors=errors, student=student)


@bp.route("/<int:pk>")
@roles_required("faculty", "admin")
def detail(pk):
    student = students_repo.get_by_id(pk)
    if student is None:
        abort(404)
    assessments = assessments_repo.list_for_student(pk)
    quiz_scores = [a["score_pct"] for a in assessments if a["assessment_type"] in ("quiz", "test")]
    prediction = predictions_repo.latest_for_student(pk)
    explanation = predictions_repo.parse_explanation(prediction) if prediction else {}
    return render_template(
        "students/detail.html", student=student, assessments=assessments,
        trend=compute_score_trend(quiz_scores), prediction=prediction, explanation=explanation,
        history=predictions_repo.history_for_student(pk),
        observations=build_observations(student, quiz_scores, settings_repo.get_all()),
        interventions=interventions_repo.list_for_student(pk),
        alerts=alerts_repo.list_for_student(pk),
        login_account=users_repo.get_by_student_fk(pk),
        model=model_status(), today=date.today().isoformat(),
        assessment_types=assessments_repo.TYPES,
    )


@bp.route("/<int:pk>/delete", methods=["POST"])
@roles_required("faculty", "admin")
def delete(pk):
    student = students_repo.get_by_id(pk)
    if student is None:
        abort(404)
    students_repo.delete(pk)
    audit.log(g.user["id"], "student_deleted", "student", pk, student["student_id"])
    flash(f"Student {student['student_id']} and all related records were deleted.", "success")
    return redirect(url_for("students.list_students"))


@bp.route("/<int:pk>/predict", methods=["POST"])
@roles_required("faculty", "admin")
def predict(pk):
    student = students_repo.get_by_id(pk)
    if student is None:
        abort(404)
    try:
        result = predict_for_students([student], g.user["id"])
        level = next(k for k, v in result["counts"].items() if v)
        flash(f"Prediction generated with model {result['model_version']}: {level} Risk.", "success")
    except (ModelUnavailable, ArtifactError) as exc:
        flash(str(exc), "danger")
    return redirect(url_for("students.detail", pk=pk))


@bp.route("/<int:pk>/assessments", methods=["POST"])
@roles_required("faculty", "admin")
def add_assessment(pk):
    student = students_repo.get_by_id(pk)
    if student is None:
        abort(404)
    a_type = request.form.get("assessment_type", "")
    title = request.form.get("title", "").strip()
    recorded_on = request.form.get("recorded_on", "").strip()
    errors = []
    if a_type not in assessments_repo.TYPES:
        errors.append("Invalid assessment type.")
    if not 1 <= len(title) <= 80:
        errors.append("Title must be 1-80 characters.")
    try:
        score = float(request.form.get("score_pct", ""))
        if not 0 <= score <= 100:
            raise ValueError
    except ValueError:
        errors.append("Score must be a number between 0 and 100.")
        score = None
    try:
        date.fromisoformat(recorded_on)
    except ValueError:
        errors.append("Date must be a valid date (YYYY-MM-DD).")
    if errors:
        for e in errors:
            flash(e, "danger")
    else:
        assessments_repo.create(pk, a_type, title, score, recorded_on)
        audit.log(g.user["id"], "assessment_added", "student", pk, title)
        flash("Assessment recorded.", "success")
    return redirect(url_for("students.detail", pk=pk) + "#assessments")


@bp.route("/<int:pk>/assessments/<int:aid>/delete", methods=["POST"])
@roles_required("faculty", "admin")
def delete_assessment(pk, aid):
    assessments_repo.delete(aid, pk)
    flash("Assessment removed.", "success")
    return redirect(url_for("students.detail", pk=pk) + "#assessments")
