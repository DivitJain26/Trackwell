from pathlib import Path

from flask import (Blueprint, Response, abort, current_app, flash, g, redirect, render_template, request,
                   session, url_for)

from app.services import csv_import
from app.services.auth import roles_required

bp = Blueprint("imports", __name__, url_prefix="/import")


@bp.route("/", methods=["GET"])
@roles_required("faculty", "admin")
def upload():
    return render_template("imports/upload.html", columns=csv_import.TEMPLATE_COLUMNS)


@bp.route("/template.csv")
@roles_required("faculty", "admin")
def template():
    return Response(csv_import.template_csv(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=trackwell_student_template.csv"})


@bp.route("/preview", methods=["POST"])
@roles_required("faculty", "admin")
def preview():
    file = request.files.get("file")
    if file is None or not file.filename:
        flash("Please choose a CSV file to upload.", "danger")
        return redirect(url_for("imports.upload"))
    ext = Path(file.filename).suffix.lower().lstrip(".")
    if ext not in current_app.config["ALLOWED_UPLOAD_EXTENSIONS"]:
        flash("Only .csv files are accepted.", "danger")
        return redirect(url_for("imports.upload"))
    try:
        df = csv_import.parse_csv(file.read())
    except csv_import.CSVParseError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("imports.upload"))
    report = csv_import.build_validation_report(df)
    token = csv_import.save_pending(report, current_app.config["UPLOAD_DIR"], Path(file.filename).name)
    session["import_token"] = token
    return render_template("imports/preview.html", report=report, filename=Path(file.filename).name,
                           columns=csv_import.TEMPLATE_COLUMNS, token=token)


@bp.route("/confirm", methods=["POST"])
@roles_required("faculty", "admin")
def confirm():
    token = request.form.get("token", "")
    if not token or token != session.get("import_token"):
        flash("The import session has expired. Please upload the file again.", "warning")
        return redirect(url_for("imports.upload"))
    pending = csv_import.load_pending(token, current_app.config["UPLOAD_DIR"])
    if pending is None:
        flash("The import session has expired. Please upload the file again.", "warning")
        return redirect(url_for("imports.upload"))
    report = pending["report"]
    if not report["can_import"]:
        abort(400)
    if report["summary"]["invalid"] and request.form.get("acknowledge_invalid") != "1":
        flash("Please confirm that invalid rows should be skipped before importing.", "warning")
        return render_template("imports/preview.html", report=report, filename=pending["filename"],
                               columns=csv_import.TEMPLATE_COLUMNS, token=token)
    on_existing = "update" if request.form.get("on_existing") == "update" else "skip"
    result = csv_import.perform_import(report, on_existing, g.user["id"])
    csv_import.discard_pending(token, current_app.config["UPLOAD_DIR"])
    session.pop("import_token", None)
    flash(
        f"Import complete: {result['inserted']} added, {result['updated']} updated, "
        f"{result['skipped_existing']} existing skipped, {result['skipped_invalid']} invalid rows skipped.",
        "success",
    )
    return redirect(url_for("students.list_students"))


@bp.route("/cancel", methods=["POST"])
@roles_required("faculty", "admin")
def cancel():
    token = session.pop("import_token", None)
    if token:
        csv_import.discard_pending(token, current_app.config["UPLOAD_DIR"])
    flash("Import cancelled. No records were changed.", "info")
    return redirect(url_for("imports.upload"))
