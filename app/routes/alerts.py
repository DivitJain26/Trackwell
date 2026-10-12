from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from app.models import alerts as alerts_repo, audit
from app.services.auth import roles_required

bp = Blueprint("alerts", __name__, url_prefix="/alerts")


@bp.route("/")
@roles_required("faculty", "admin")
def index():
    status = request.args.get("status", "new")
    if status not in ("new", "reviewed", "all"):
        status = "new"
    rows = alerts_repo.list_alerts("" if status == "all" else status)
    return render_template("alerts/list.html", alerts=rows, status=status,
                           new_count=alerts_repo.count_new())


@bp.route("/<int:pk>/review", methods=["POST"])
@roles_required("faculty", "admin")
def review(pk):
    alert = alerts_repo.get_by_id(pk)
    if alert is None:
        abort(404)
    alerts_repo.mark_reviewed(pk, g.user["id"])
    audit.log(g.user["id"], "alert_reviewed", "alert", pk)
    if request.form.get("then") == "intervene":
        return redirect(url_for("interventions.new", student=alert["student_fk"], alert=pk))
    flash("Alert marked as reviewed.", "success")
    return redirect(request.form.get("next") or url_for("alerts.index"))
