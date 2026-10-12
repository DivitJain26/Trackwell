"""Validation rules for student records.

The same function validates web-form input and CSV rows so both paths behave
identically. Values arrive as strings (or None) and are converted to the
correct Python types.
"""
import math
import re

from app.models.students import FIELDS

LEVELS = ("Low", "Medium", "High")
STUDENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-/]{0,29}$")

REQUIRED = ("student_id", "name", "class_name", "semester", "attendance_pct",
            "assignment_completion_pct", "participation", "engagement_level")

NUMERIC_RANGES = {
    "attendance_pct": (0, 100, "Attendance %"),
    "previous_gpa": (0, 10, "Previous GPA"),
    "quiz_score": (0, 100, "Quiz score"),
    "test_score": (0, 100, "Test score"),
    "assignment_completion_pct": (0, 100, "Assignment completion %"),
    "study_hours": (0, 16, "Study hours"),
}


def _is_blank(value) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return str(value).strip() == ""


def _to_float(value, field_label: str, lo: float, hi: float, errors: list):
    try:
        number = float(str(value).strip().rstrip("%"))
    except (TypeError, ValueError):
        errors.append(f"{field_label} must be a number (got '{value}').")
        return None
    if math.isnan(number) or math.isinf(number):
        errors.append(f"{field_label} must be a finite number.")
        return None
    if not (lo <= number <= hi):
        errors.append(f"{field_label} must be between {lo:g} and {hi:g} (got {number:g}).")
        return None
    return round(number, 2)


def _to_level(value, field_label: str, errors: list):
    text = str(value).strip().title()
    if text not in LEVELS:
        errors.append(f"{field_label} must be one of Low, Medium or High (got '{value}').")
        return None
    return text


def validate_student_record(raw: dict) -> tuple[dict, list[str]]:
    """Return ``(clean_record, errors)``. ``clean_record`` is complete only if no errors."""
    errors: list[str] = []
    clean: dict = {f: None for f in FIELDS}

    for field in REQUIRED:
        if _is_blank(raw.get(field)):
            errors.append(f"{field} is required.")

    sid = str(raw.get("student_id") or "").strip()
    if sid:
        if not STUDENT_ID_RE.match(sid):
            errors.append("student_id may contain only letters, digits, '-', '_' or '/' (max 30 chars).")
        clean["student_id"] = sid.upper()

    name = str(raw.get("name") or "").strip()
    if name and not (2 <= len(name) <= 100):
        errors.append("name must be between 2 and 100 characters.")
    clean["name"] = name or None

    class_name = str(raw.get("class_name") or "").strip()
    if class_name and len(class_name) > 50:
        errors.append("class_name must be at most 50 characters.")
    clean["class_name"] = class_name or None

    if not _is_blank(raw.get("semester")):
        try:
            sem = int(float(str(raw["semester"]).strip()))
            if not 1 <= sem <= 8:
                errors.append(f"semester must be between 1 and 8 (got {sem}).")
            else:
                clean["semester"] = sem
        except (TypeError, ValueError):
            errors.append(f"semester must be a whole number (got '{raw.get('semester')}').")

    for field, (lo, hi, label) in NUMERIC_RANGES.items():
        if not _is_blank(raw.get(field)):
            clean[field] = _to_float(raw.get(field), label, lo, hi, errors)

    for field, label in (("participation", "participation"), ("engagement_level", "engagement_level")):
        if not _is_blank(raw.get(field)):
            clean[field] = _to_level(raw.get(field), label, errors)

    if not _is_blank(raw.get("self_understanding")):
        try:
            su = int(float(str(raw["self_understanding"]).strip()))
            if not 1 <= su <= 5:
                errors.append(f"self_understanding must be between 1 and 5 (got {su}).")
            else:
                clean["self_understanding"] = su
        except (TypeError, ValueError):
            errors.append(f"self_understanding must be a whole number 1-5 (got '{raw.get('self_understanding')}').")

    return clean, errors
