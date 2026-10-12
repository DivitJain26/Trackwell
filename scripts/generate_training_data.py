"""Generate the SYNTHETIC demonstration training dataset.

The data is produced by a documented random process and does NOT describe real
students. It exists so the ML pipeline can be demonstrated end-to-end. Model
metrics on this data say nothing about real-world predictive performance.

Run:  python scripts/generate_training_data.py [--rows 1500] [--seed 42]
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.ml.train import label_from_final_exam  # noqa: E402


def generate(rows: int = 1500, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    # Latent "academic standing" drives all indicators, with independent noise so
    # that no single input determines the label.
    ability = rng.normal(0, 1, rows)
    effort = 0.6 * ability + rng.normal(0, 0.8, rows)

    attendance = np.clip(76 + 9 * effort + rng.normal(0, 8, rows), 30, 100)
    previous_gpa = np.clip(6.8 + 1.1 * ability + rng.normal(0, 0.7, rows), 3.0, 10.0)
    quiz = np.clip(60 + 13 * ability + 4 * effort + rng.normal(0, 10, rows), 0, 100)
    test = np.clip(58 + 14 * ability + 3 * effort + rng.normal(0, 11, rows), 0, 100)
    assignment = np.clip(74 + 11 * effort + rng.normal(0, 12, rows), 0, 100)
    study_hours = np.clip(2.4 + 0.9 * effort + rng.normal(0, 0.8, rows), 0, 9).round(1)
    understanding = np.clip(np.rint(3.1 + 0.8 * ability + rng.normal(0, 0.8, rows)), 1, 5).astype(int)
    quiz_trend = rng.normal(0, 8, rows) + 2.5 * effort

    def level(z, noise=0.7):
        v = z + rng.normal(0, noise, rows)
        return np.where(v < -0.5, "Low", np.where(v < 0.6, "Medium", "High"))

    participation = level(effort)
    engagement = level(0.5 * effort + 0.5 * ability)

    # Final exam outcome (the quantity the label is derived from). It depends on
    # the indicators above plus substantial unexplained variation.
    final = (
        51
        + 9.5 * ability
        + 0.18 * (attendance - 76)
        + 0.16 * (quiz - 60)
        + 0.16 * (test - 58)
        + 0.08 * (assignment - 74)
        + 1.6 * (study_hours - 2.4)
        + 1.8 * (understanding - 3)
        + 0.12 * quiz_trend
        + rng.normal(0, 9, rows)
    )
    final = np.clip(final, 0, 100)

    # Introduce a small amount of missing data, as real collections have gaps.
    def with_missing(arr, frac):
        arr = arr.astype(float)
        mask = rng.random(rows) < frac
        arr[mask] = np.nan
        return arr

    df = pd.DataFrame({
        "attendance_pct": attendance.round(1),
        "previous_gpa": with_missing(previous_gpa.round(2), 0.04),
        "quiz_score": quiz.round(1),
        "test_score": with_missing(test.round(1), 0.03),
        "assignment_completion_pct": assignment.round(1),
        "study_hours": with_missing(study_hours, 0.05),
        "participation": participation,
        "engagement_level": engagement,
        "self_understanding": understanding,
        "quiz_trend": with_missing(quiz_trend.round(1), 0.15),
        "final_exam_pct": final.round(1),
    })
    df["risk_label"] = df["final_exam_pct"].map(label_from_final_exam)
    return df


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=1500)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "training_data.csv")
    args = parser.parse_args()
    df = generate(args.rows, args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False)
    print(f"Wrote {len(df)} synthetic rows to {args.out}")
    print(df["risk_label"].value_counts().to_string())


if __name__ == "__main__":
    main()
