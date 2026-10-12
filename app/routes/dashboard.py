from flask import Blueprint, render_template

from app.models import alerts as alerts_repo, students as students_repo
from app.services.auth import roles_required
from app.services.dashboard_service import faculty_summary

bp = Blueprint("dashboard", __name__)


@bp.route("/dashboard")
@roles_required("faculty", "admin")
def index():
    summary = faculty_summary()
    high_risk = students_repo.search(risk_level="High", sort="risk", limit=10)
    return render_template("dashboard/index.html", summary=summary, high_risk=high_risk,
                           recent_alerts=alerts_repo.list_alerts(status="new", limit=8))
