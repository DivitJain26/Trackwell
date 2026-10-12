from flask import Blueprint, g, redirect, render_template, url_for

from app.services.auth import home_url_for, login_required

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    if g.get("user") is None:
        return redirect(url_for("auth.login"))
    return redirect(home_url_for(g.user))


@bp.route("/documentation")
@login_required
def documentation():
    return render_template("docs/documentation.html")
