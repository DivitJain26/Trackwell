"""Model training and evaluation.

Usage (from the project root, inside the virtual environment)::

    python scripts/train_model.py

The function :func:`train_and_evaluate` is framework-independent so the same
code is used by the CLI script, the web UI and the tests.

Target definition
-----------------
The training CSV contains ``final_exam_pct`` (the end-of-semester exam result)
from which ``risk_label`` is derived:

* ``High``   - final exam below 40 % (fail)
* ``Medium`` - 40 % to below 55 % (borderline pass)
* ``Low``    - 55 % and above

``final_exam_pct`` and ``risk_label`` are *never* used as model inputs.

Model selection
---------------
Each candidate is evaluated with stratified 5-fold cross-validation on the
training split and then on a held-out test split (20 %). The final model is
the one with the highest *selection score* on the held-out split:

    selection_score = 0.5 * macro F1 + 0.5 * recall(High)

This favours models that catch students needing support over raw accuracy.
"""
from __future__ import annotations

import platform
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.metrics import (accuracy_score, classification_report, confusion_matrix,
                             f1_score, precision_score, recall_score)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split

from app.ml.artifacts import save_artifact
from app.ml.features import (ALL_FEATURES, CATEGORICAL_FEATURES, CLASSES, NUMERIC_FEATURES,
                             RAW_CATEGORICAL, RAW_NUMERIC, TARGET, build_feature_frame)
from app.ml.pipeline import build_pipeline, candidate_estimators

RANDOM_STATE = 42


class TrainingError(RuntimeError):
    pass


def label_from_final_exam(final_pct: float) -> str:
    if final_pct < 40:
        return "High"
    if final_pct < 55:
        return "Medium"
    return "Low"


def load_training_data(csv_path: Path) -> pd.DataFrame:
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise TrainingError(f"Training dataset not found: {csv_path}")
    df = pd.read_csv(csv_path)
    if TARGET not in df.columns:
        if "final_exam_pct" not in df.columns:
            raise TrainingError(
                "Training data must contain a 'risk_label' column or a 'final_exam_pct' column."
            )
        df[TARGET] = pd.to_numeric(df["final_exam_pct"], errors="coerce").map(label_from_final_exam)
    df = df[df[TARGET].isin(CLASSES)].copy()
    missing = [c for c in RAW_NUMERIC + RAW_CATEGORICAL if c not in df.columns and c != "quiz_trend"]
    if missing:
        raise TrainingError(f"Training data is missing required columns: {', '.join(missing)}")
    if len(df) < 100:
        raise TrainingError("Training data must contain at least 100 labelled rows.")
    counts = df[TARGET].value_counts()
    if (counts < 10).any():
        raise TrainingError("Each risk class needs at least 10 labelled rows for training.")
    return df


def _metrics(y_true, y_pred) -> dict:
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision_macro": float(precision_score(y_true, y_pred, average="macro", zero_division=0)),
        "recall_macro": float(recall_score(y_true, y_pred, average="macro", zero_division=0)),
        "f1_macro": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "recall_high": float(recall_score(y_true, y_pred, labels=["High"], average="macro", zero_division=0)),
        "precision_high": float(precision_score(y_true, y_pred, labels=["High"], average="macro", zero_division=0)),
        "per_class": {
            k: v for k, v in classification_report(
                y_true, y_pred, labels=CLASSES, output_dict=True, zero_division=0
            ).items() if k in CLASSES
        },
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=CLASSES).tolist(),
    }


def _reference_values(X_train: pd.DataFrame) -> dict:
    """Median / mode of each raw feature on the training split (for explanations)."""
    ref = {}
    for col in RAW_NUMERIC:
        series = pd.to_numeric(X_train[col], errors="coerce")
        ref[col] = None if series.isna().all() else float(series.median())
    for col in RAW_CATEGORICAL:
        mode = X_train[col].dropna().mode()
        ref[col] = None if mode.empty else str(mode.iloc[0])
    return ref


def _global_importance(pipeline) -> list[dict]:
    """Feature importance of the fitted estimator mapped back to feature names."""
    model = pipeline.named_steps["model"]
    pre = pipeline.named_steps["preprocess"]
    names = list(pre.get_feature_names_out())
    if hasattr(model, "feature_importances_"):
        raw = np.asarray(model.feature_importances_, dtype=float)
        kind = "tree_feature_importance"
    elif hasattr(model, "coef_"):
        raw = np.mean(np.abs(model.coef_), axis=0)
        kind = "mean_abs_coefficient"
    else:
        return []
    # Collapse one-hot columns back to their source feature.
    grouped: dict[str, float] = {}
    for name, value in zip(names, raw):
        base = name.split("__", 1)[1]
        for feat in CATEGORICAL_FEATURES:
            if base.startswith(feat + "_"):
                base = feat
                break
        grouped[base] = grouped.get(base, 0.0) + float(value)
    total = sum(grouped.values()) or 1.0
    items = [{"feature": k, "importance": v / total, "kind": kind} for k, v in grouped.items()]
    return sorted(items, key=lambda d: d["importance"], reverse=True)


def train_and_evaluate(csv_path: Path, model_dir: Path, version: str, quick: bool = False,
                       dataset_source: str | None = None) -> dict:
    """Train candidate models, select the best, save the artifact and return a report."""
    df = load_training_data(csv_path)
    X_raw = df.drop(columns=[c for c in ("final_exam_pct", TARGET) if c in df.columns])
    y = df[TARGET].astype(str)

    X_train_raw, X_test_raw, y_train, y_test = train_test_split(
        X_raw, y, test_size=0.2, stratify=y, random_state=RANDOM_STATE
    )
    X_train = build_feature_frame(X_train_raw)
    X_test = build_feature_frame(X_test_raw)

    candidates = []
    fitted = {}
    cv = StratifiedKFold(n_splits=3 if quick else 5, shuffle=True, random_state=RANDOM_STATE)
    for name, estimator in candidate_estimators(quick=quick).items():
        pipe = build_pipeline(estimator)
        cv_scores = cross_val_score(pipe, X_train, y_train, cv=cv, scoring="f1_macro")
        pipe.fit(X_train, y_train)
        y_pred = pipe.predict(X_test)
        m = _metrics(y_test, y_pred)
        m["cv_f1_macro_mean"] = float(np.mean(cv_scores))
        m["cv_f1_macro_std"] = float(np.std(cv_scores))
        m["selection_score"] = 0.5 * m["f1_macro"] + 0.5 * m["recall_high"]
        candidates.append({"name": name, "metrics": m})
        fitted[name] = pipe

    best = max(candidates, key=lambda c: c["metrics"]["selection_score"])
    best_pipe = fitted[best["name"]]
    # Final refit on all labelled data so the deployed model uses every example.
    X_all = build_feature_frame(X_raw)
    best_pipe.fit(X_all, y)

    feature_schema = {
        "raw_numeric": RAW_NUMERIC,
        "raw_categorical": RAW_CATEGORICAL,
        "model_features": ALL_FEATURES,
        "numeric_features": NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "target": TARGET,
        "classes": CLASSES,
        "target_definition": "High: final_exam_pct < 40; Medium: 40 <= final_exam_pct < 55; Low: >= 55",
    }
    trained_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    payload = {
        "version": version,
        "algorithm": best["name"],
        "trained_at": trained_at,
        "pipeline": best_pipe,
        "feature_schema": feature_schema,
        "reference_values": _reference_values(X_raw),
        "classes": list(best_pipe.classes_),
        "global_importance": _global_importance(best_pipe),
        "sklearn_version": sklearn.__version__,
        "python_version": platform.python_version(),
    }
    artifact_path, digest = save_artifact(payload, Path(model_dir), version)

    return {
        "version": version,
        "algorithm": best["name"],
        "trained_at": trained_at,
        "dataset_source": dataset_source or str(csv_path),
        "dataset_rows": int(len(df)),
        "class_distribution": y.value_counts().to_dict(),
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
        "metrics": best["metrics"],
        "candidates": candidates,
        "feature_schema": feature_schema,
        "global_importance": payload["global_importance"],
        "artifact_path": str(artifact_path),
        "artifact_sha256": digest,
        "selection_rule": "0.5 * macro F1 + 0.5 * recall(High) on the 20% held-out split",
        "sklearn_version": sklearn.__version__,
    }
