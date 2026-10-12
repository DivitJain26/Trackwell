"""Student-facing portal: a student sees only their own record."""
from flask import Blueprint, abort, g, render_template

from app.ml.features import compute_score_trend
from app.models import assessments as assessments_repo
from app.models import interventions as interventions_repo
from app.models import predictions as predictions_repo
from app.models import settings as settings_repo
from app.models import students as students_repo
from app.services.auth import roles_required
from app.services.observations import build_observations, build_suggestions

bp = Blueprint("portal", __name__, url_prefix="/me")


@bp.route("/")
@roles_required("student")
def index():
    if not g.user["student_fk"]:
        return render_template("portal/unlinked.html")
    student = students_repo.get_by_id(g.user["student_fk"])
    if student is None:
        abort(404)
    assessments = assessments_repo.list_for_student(student["id"])
    quiz_scores = [a["score_pct"] for a in assessments if a["assessment_type"] in ("quiz", "test")]
    settings = settings_repo.get_all()
    observations = build_observations(student, quiz_scores, settings)
    show_risk = settings_repo.get_bool("show_risk_to_students")
    prediction = predictions_repo.latest_for_student(student["id"]) if show_risk else None
    explanation = predictions_repo.parse_explanation(prediction) if prediction else {}
    # Students see only the type/date/status of interventions, never faculty notes.
    interventions = [
        {"intervention_date": i["intervention_date"], "intervention_type": i["intervention_type"],
         "status": i["status"], "follow_up_date": i["follow_up_date"]}
        for i in interventions_repo.list_for_student(student["id"])
    ]
    return render_template("portal/index.html", student=student, assessments=assessments,
                           trend=compute_score_trend(quiz_scores), observations=observations,
                           suggestions=build_suggestions(observations), prediction=prediction,
                           explanation=explanation, show_risk=show_risk, interventions=interventions,
                           settings=settings)
