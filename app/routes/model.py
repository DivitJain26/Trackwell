from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, url_for

from app.ml.features import FEATURE_LABELS
from app.models import audit, model_versions
from app.services.auth import roles_required
from app.services.model_service import TrainingError, model_status, train_new_version

bp = Blueprint("model", __name__, url_prefix="/model")


@bp.route("/")
@roles_required("faculty", "admin")
def index():
    versions = [model_versions.parse(r) for r in model_versions.list_all()]
    active = next((v for v in versions if v["is_active"]), None)
    training_path = current_app.config["TRAINING_DATA"]
    return render_template("model/index.html", versions=versions, active=active, status=model_status(),
                           training_path=training_path, training_exists=training_path.exists())


@bp.route("/<int:pk>")
@roles_required("faculty", "admin")
def detail(pk):
    version = model_versions.parse(model_versions.get_by_id(pk))
    if version is None:
        abort(404)
    return render_template("model/detail.html", v=version, feature_labels=FEATURE_LABELS)


@bp.route("/train", methods=["POST"])
@roles_required("admin", "faculty")
def train():
    notes = request.form.get("notes", "").strip()[:500]
    try:
        report = train_new_version(g.user["id"], notes=notes)
        m = report["metrics"]
        flash(
            f"Model {report['version']} trained ({report['algorithm']}): macro F1 {m['f1_macro']:.2f}, "
            f"High-risk recall {m['recall_high']:.2f} on the held-out split. It is now the active model.",
            "success",
        )
        return redirect(url_for("model.detail", pk=report["id"]))
    except TrainingError as exc:
        flash(f"Training failed: {exc}", "danger")
    except Exception:  # pragma: no cover - logged, generic message shown
        current_app.logger.exception("Model training failed")
        flash("Training failed because of an unexpected error. See the local log for details.", "danger")
    return redirect(url_for("model.index"))


@bp.route("/<int:pk>/activate", methods=["POST"])
@roles_required("admin")
def activate(pk):
    row = model_versions.get_by_id(pk)
    if row is None:
        abort(404)
    model_versions.activate(pk)
    from app.services import model_service
    model_service._cache["key"] = None
    audit.log(g.user["id"], "model_activated", "model_version", pk, row["version"])
    flash(f"Model {row['version']} is now active.", "success")
    return redirect(url_for("model.index"))
