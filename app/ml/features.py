"""Feature engineering shared by training and inference.

Everything the model sees passes through :func:`build_feature_frame`, so the
training and prediction paths cannot drift apart. Columns that would only be
known *after* the outcome (e.g. the final exam score used to derive the
training label) are never part of the feature set - this prevents target
leakage.
"""
import numpy as np
import pandas as pd

# Raw inputs collected for each student (all available before final exams).
RAW_NUMERIC = [
    "attendance_pct",
    "previous_gpa",
    "quiz_score",
    "test_score",
    "assignment_completion_pct",
    "study_hours",
    "self_understanding",
    "quiz_trend",
]
RAW_CATEGORICAL = ["participation", "engagement_level"]
RAW_FEATURES = RAW_NUMERIC + RAW_CATEGORICAL

# Derived features added by build_feature_frame.
DERIVED_NUMERIC = ["avg_score"]
DERIVED_CATEGORICAL = ["attendance_level"]

NUMERIC_FEATURES = RAW_NUMERIC + DERIVED_NUMERIC
CATEGORICAL_FEATURES = RAW_CATEGORICAL + DERIVED_CATEGORICAL
ALL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

TARGET = "risk_label"
CLASSES = ["Low", "Medium", "High"]

# Columns present in the training CSV that must NEVER be used as features.
LEAKAGE_COLUMNS = ["final_exam_pct", TARGET]

LEVEL_ORDER = {"Low": 0, "Medium": 1, "High": 2}

FEATURE_LABELS = {
    "attendance_pct": "Attendance (%)",
    "previous_gpa": "Previous GPA / SGPA",
    "quiz_score": "Average quiz score (%)",
    "test_score": "Average test score (%)",
    "assignment_completion_pct": "Assignment completion (%)",
    "study_hours": "Daily study hours",
    "self_understanding": "Self-reported understanding (1-5)",
    "quiz_trend": "Recent score trend",
    "participation": "Class participation",
    "engagement_level": "Engagement level",
    "avg_score": "Average of quiz and test scores",
    "attendance_level": "Attendance band",
}


def attendance_band(value) -> str | float:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return np.nan
    if value < 65:
        return "Low"
    if value < 75:
        return "Borderline"
    return "Good"


def compute_score_trend(scores: list[float] | None) -> float | None:
    """Difference between the mean of the later half and earlier half of scores.

    Returns ``None`` when fewer than two scores exist (imputed downstream).
    Positive values mean improving scores; negative values mean a decline.
    """
    if not scores or len(scores) < 2:
        return None
    arr = np.asarray(scores, dtype=float)
    half = len(arr) // 2
    earlier = arr[:half] if half else arr[:1]
    later = arr[half:]
    return float(np.mean(later) - np.mean(earlier))


def build_feature_frame(raw: pd.DataFrame) -> pd.DataFrame:
    """Return the model input frame from raw student records.

    Missing raw columns are added as NaN so the imputers in the pipeline can
    handle them. Leakage columns are dropped if present.
    """
    df = raw.copy()
    for col in RAW_FEATURES:
        if col not in df.columns:
            df[col] = np.nan
    for col in RAW_NUMERIC:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)
    for col in RAW_CATEGORICAL:
        df[col] = df[col].astype(object).where(df[col].notna(), None)

    df["avg_score"] = df[["quiz_score", "test_score"]].mean(axis=1, skipna=True)
    df["attendance_level"] = df["attendance_pct"].map(attendance_band).astype(object)

    df = df.drop(columns=[c for c in LEAKAGE_COLUMNS if c in df.columns])
    return df[ALL_FEATURES]


def student_row_to_raw(student_row, quiz_scores: list[float] | None = None) -> dict:
    """Convert a ``students`` database row (sqlite3.Row/dict) to raw feature dict."""
    s = dict(student_row)
    return {
        "attendance_pct": s.get("attendance_pct"),
        "previous_gpa": s.get("previous_gpa"),
        "quiz_score": s.get("quiz_score"),
        "test_score": s.get("test_score"),
        "assignment_completion_pct": s.get("assignment_completion_pct"),
        "study_hours": s.get("study_hours"),
        "self_understanding": s.get("self_understanding"),
        "quiz_trend": compute_score_trend(quiz_scores),
        "participation": s.get("participation"),
        "engagement_level": s.get("engagement_level"),
    }
