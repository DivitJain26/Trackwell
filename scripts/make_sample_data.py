"""Generate the SYNTHETIC demo student roster and assessment history.

Writes data/sample_students.csv and data/sample_assessments.csv. Names are
fictional; nothing here describes real students.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FIRST = ["Aarav", "Ananya", "Vihaan", "Diya", "Arjun", "Ishaan", "Saanvi", "Kabir", "Meera", "Rohan",
         "Priya", "Aditya", "Kavya", "Dev", "Nisha", "Yash", "Riya", "Om", "Tanvi", "Shaurya",
         "Pooja", "Harsh", "Sneha", "Kunal", "Avni", "Neel", "Isha", "Manav", "Shreya", "Varun",
         "Anika", "Rudra", "Mahi", "Siddharth", "Trisha", "Atharv", "Kiara", "Parth", "Naina", "Ayaan",
         "Sara", "Vivaan", "Pari", "Reyansh", "Myra"]
LAST = ["Sharma", "Patil", "Deshmukh", "Kulkarni", "Joshi", "Jadhav", "Pawar", "Shinde", "More", "Gaikwad",
        "Bhosale", "Chavan", "Mehta", "Iyer", "Nair", "Reddy", "Singh", "Verma", "Gupta", "Kadam"]
CLASSES = [("TY CSE A", 5), ("TY CSE B", 5), ("SY CSE A", 3)]


def main(seed: int = 7):
    rng = np.random.default_rng(seed)
    rows, assessments = [], []
    n = 0
    for class_name, semester in CLASSES:
        for _ in range(15):
            n += 1
            ability = rng.normal(0, 1)
            effort = 0.6 * ability + rng.normal(0, 0.8)
            att = float(np.clip(76 + 9 * effort + rng.normal(0, 8), 35, 100))
            quiz = float(np.clip(60 + 13 * ability + 4 * effort + rng.normal(0, 10), 5, 100))
            test = float(np.clip(58 + 14 * ability + 3 * effort + rng.normal(0, 11), 5, 100))
            lvl = lambda z: "Low" if z < -0.5 else ("Medium" if z < 0.6 else "High")  # noqa: E731
            sid = f"CSE{'22' if semester == 5 else '23'}{n:03d}"
            rows.append({
                "student_id": sid,
                "name": f"{rng.choice(FIRST)} {rng.choice(LAST)}",
                "class_name": class_name, "semester": semester,
                "attendance_pct": round(att, 1),
                "previous_gpa": "" if rng.random() < 0.05 else round(float(np.clip(6.8 + 1.1 * ability + rng.normal(0, 0.7), 3, 10)), 2),
                "quiz_score": round(quiz, 1), "test_score": round(test, 1),
                "assignment_completion_pct": round(float(np.clip(74 + 11 * effort + rng.normal(0, 12), 0, 100)), 1),
                "study_hours": round(float(np.clip(2.4 + 0.9 * effort + rng.normal(0, 0.8), 0, 9)), 1),
                "participation": lvl(effort + rng.normal(0, 0.7)),
                "engagement_level": lvl(0.5 * effort + 0.5 * ability + rng.normal(0, 0.7)),
                "self_understanding": int(np.clip(np.rint(3.1 + 0.8 * ability + rng.normal(0, 0.8)), 1, 5)),
            })
            # 3-4 historical quizzes/tests with an individual trend
            trend = rng.normal(0, 6)
            base = (quiz + test) / 2
            dates = ["2026-07-20", "2026-08-10", "2026-08-31", "2026-09-21"]
            for k, d in enumerate(dates[: int(rng.integers(3, 5))]):
                score = float(np.clip(base + trend * (k - 1.5) + rng.normal(0, 6), 0, 100))
                assessments.append({"student_id": sid, "assessment_type": "quiz" if k % 2 == 0 else "test",
                                    "title": f"{'Quiz' if k % 2 == 0 else 'Unit test'} {k // 2 + 1}",
                                    "score_pct": round(score, 1), "recorded_on": d})
    pd.DataFrame(rows).to_csv(ROOT / "data" / "sample_students.csv", index=False)
    pd.DataFrame(assessments).to_csv(ROOT / "data" / "sample_assessments.csv", index=False)
    print(f"Wrote {len(rows)} synthetic students and {len(assessments)} assessments to data/")


if __name__ == "__main__":
    main()
