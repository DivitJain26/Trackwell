import io
from datetime import date

import pandas as pd
from flask import Blueprint, Response, flash, g, redirect, render_template, request, url_for

from app.models import predictions as predictions_repo
from app.models import students as students_repo
from app.services.auth import roles_required
from app.services.model_service import ArtifactError, model_status
from app.services.prediction_service import ModelUnavailable, predict_for_students

bp = Blueprint("predictions", __name__, url_prefix="/predictions")


def _filters():
    return {
        "class_name": request.args.get("class_name", "").strip(),
        "semester": request.args.get("semester", "").strip(),
        "risk": request.args.get("risk", "").strip(),
    }


@bp.route("/")
@roles_required("faculty", "admin")
def index():
    f = _filters()
    rows = predictions_repo.latest_all(f["class_name"], f["semester"], f["risk"])
    return render_template("predictions/list.html", predictions=rows, filters=f,
                           classes=students_repo.distinct_classes(),
                           semesters=students_repo.distinct_semesters(),
                           counts=predictions_repo.risk_counts(), model=model_status(),
                           total_students=students_repo.count(),
                           parse=predictions_repo.parse_explanation)


@bp.route("/run", methods=["POST"])
@roles_required("faculty", "admin")
def run():
    scope = request.form.get("scope", "all")
    class_name = request.form.get("class_name", "").strip()
    if scope == "class" and class_name:
        rows = students_repo.search(class_name=class_name)
    elif scope == "unpredicted":
        rows = students_repo.search(risk_level="none")
    else:
        rows = students_repo.list_all()
    if not rows:
        flash("There are no students matching the selected scope.", "warning")
        return redirect(url_for("predictions.index"))
    try:
        result = predict_for_students(rows, g.user["id"])
        c = result["counts"]
        flash(
            f"Predictions generated for {result['predicted']} students with model {result['model_version']}: "
            f"{c['High']} High, {c['Medium']} Medium, {c['Low']} Low. {result['alerts']} new alert(s).",
            "success",
        )
    except (ModelUnavailable, ArtifactError) as exc:
        flash(str(exc), "danger")
    return redirect(url_for("predictions.index"))


@bp.route("/export.csv")
@roles_required("faculty", "admin")
def export_csv():
    f = _filters()
    rows = predictions_repo.latest_all(f["class_name"], f["semester"], f["risk"])
    data = []
    for r in rows:
        exp = predictions_repo.parse_explanation(r)
        factors = "; ".join(f"{m['label']} ({m['contribution']:+.1f})" for m in exp.get("model_factors", [])[:3])
        data.append({
            "student_id": r["student_id"], "name": r["name"], "class_name": r["class_name"],
            "semester": r["semester"], "risk_level": r["risk_level"], "risk_score": r["risk_score"],
            "prob_low": round(r["prob_low"], 4), "prob_medium": round(r["prob_medium"], 4),
            "prob_high": round(r["prob_high"], 4), "top_model_factors": factors,
            "model_version": r["model_version"], "predicted_at": r["created_at"],
        })
    buf = io.StringIO()
    pd.DataFrame(data).to_csv(buf, index=False)
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=trackwell_predictions_{date.today()}.csv"})
