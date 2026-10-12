"""CSV upload parsing, validation report and import."""
from __future__ import annotations

import io
import json
import secrets
from pathlib import Path

import pandas as pd

from app.models import audit, students as students_repo
from app.models.students import FIELDS
from app.services.validation import validate_student_record

TEMPLATE_COLUMNS = FIELDS

TEMPLATE_ROWS = [
    ["CSE21001", "Example Student", "TY CSE A", 5, 82.5, 7.8, 68, 72, 90, 2.5, "Medium", "High", 4],
    ["CSE21002", "Second Example", "TY CSE A", 5, 61.0, 6.1, 45, 40, 55, 1.0, "Low", "Low", 2],
]


def template_csv() -> str:
    buf = io.StringIO()
    pd.DataFrame(TEMPLATE_ROWS, columns=TEMPLATE_COLUMNS).to_csv(buf, index=False)
    return buf.getvalue()


class CSVParseError(ValueError):
    pass


def parse_csv(file_bytes: bytes) -> pd.DataFrame:
    if not file_bytes or not file_bytes.strip():
        raise CSVParseError("The uploaded file is empty.")
    try:
        text = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = file_bytes.decode("latin-1")
        except UnicodeDecodeError as exc:
            raise CSVParseError("The file could not be decoded as text (UTF-8 expected).") from exc
    try:
        df = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False, skip_blank_lines=True)
    except Exception as exc:  # pandas raises several parser error types
        raise CSVParseError(f"The file could not be parsed as CSV: {exc}") from exc
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    if len(df) == 0:
        raise CSVParseError("The CSV contains a header but no data rows.")
    if len(df) > 5000:
        raise CSVParseError("At most 5000 rows can be imported at once.")
    return df


def build_validation_report(df: pd.DataFrame) -> dict:
    """Validate every row and return a report used for the preview page."""
    missing_cols = [c for c in TEMPLATE_COLUMNS if c not in df.columns]
    extra_cols = [c for c in df.columns if c not in TEMPLATE_COLUMNS]
    rows = []
    seen_ids: dict[str, int] = {}
    existing_ids = {s["student_id"].upper() for s in students_repo.list_all()}

    for idx, record in enumerate(df.to_dict(orient="records"), start=2):  # line 1 = header
        clean, errors = validate_student_record(record)
        sid = clean.get("student_id")
        status = "valid"
        if sid:
            if sid in seen_ids:
                errors.append(f"Duplicate student_id in file (also on line {seen_ids[sid]}).")
            else:
                seen_ids[sid] = idx
        if errors:
            status = "invalid"
        elif sid in existing_ids:
            status = "existing"
        rows.append({
            "line": idx,
            "status": status,
            "errors": errors,
            "raw": {k: record.get(k, "") for k in TEMPLATE_COLUMNS},
            "clean": clean if not errors else None,
        })

    summary = {
        "total": len(rows),
        "valid": sum(r["status"] == "valid" for r in rows),
        "existing": sum(r["status"] == "existing" for r in rows),
        "invalid": sum(r["status"] == "invalid" for r in rows),
    }
    return {
        "missing_columns": missing_cols,
        "extra_columns": extra_cols,
        "rows": rows,
        "summary": summary,
        "can_import": not missing_cols and (summary["valid"] + summary["existing"]) > 0,
    }


def save_pending(report: dict, upload_dir: Path, filename: str) -> str:
    """Persist a validation report so the confirm step can import it."""
    upload_dir = Path(upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(16)
    payload = {"filename": filename, "report": report}
    (upload_dir / f"pending_{token}.json").write_text(json.dumps(payload), encoding="utf-8")
    return token


def load_pending(token: str, upload_dir: Path) -> dict | None:
    if not token or not all(ch.isalnum() or ch in "-_" for ch in token):
        return None
    path = Path(upload_dir) / f"pending_{token}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def discard_pending(token: str, upload_dir: Path):
    path = Path(upload_dir) / f"pending_{token}.json"
    if path.exists():
        path.unlink()


def perform_import(report: dict, on_existing: str, user_id: int | None) -> dict:
    """Insert valid rows (and optionally update existing ones). Invalid rows are skipped and reported."""
    inserted = updated = skipped_existing = 0
    for row in report["rows"]:
        if row["status"] == "invalid":
            continue
        clean = row["clean"]
        if row["status"] == "existing":
            if on_existing == "update":
                pk, _ = students_repo.upsert_by_student_id(clean)
                updated += 1
            else:
                skipped_existing += 1
            continue
        existing = students_repo.get_by_student_id(clean["student_id"])
        if existing:  # created between preview and confirm
            if on_existing == "update":
                students_repo.update(existing["id"], clean)
                updated += 1
            else:
                skipped_existing += 1
            continue
        students_repo.create(clean)
        inserted += 1
    result = {
        "inserted": inserted,
        "updated": updated,
        "skipped_existing": skipped_existing,
        "skipped_invalid": report["summary"]["invalid"],
    }
    audit.log(user_id, "csv_import", "students", None, json.dumps(result))
    return result


def export_students_csv(rows) -> str:
    """Export student rows (with latest prediction where joined) to CSV text."""
    cols = FIELDS + ["risk_level", "risk_score", "predicted_at", "model_version"]
    data = []
    for r in rows:
        d = dict(r)
        data.append({c: d.get(c) for c in cols})
    buf = io.StringIO()
    pd.DataFrame(data, columns=cols).to_csv(buf, index=False)
    return buf.getvalue()
