"""Descriptive (rule-based) observations and student-facing suggestions.

These are NOT model explanations. They compare a student's indicators with
reference levels configured by the administrator and are always labelled as
descriptive observations in the UI. Model-derived factors come from
:mod:`app.ml.predict`.
"""
from app.ml.features import compute_score_trend


def build_observations(student, quiz_scores: list[float] | None, settings: dict) -> list[dict]:
    s = dict(student)
    att_ref = float(settings.get("attendance_reference", 75))
    asg_ref = float(settings.get("assignment_reference", 70))
    score_ref = float(settings.get("score_reference", 50))
    hours_ref = float(settings.get("study_hours_reference", 2))
    obs: list[dict] = []

    if s.get("attendance_pct") is not None and s["attendance_pct"] < att_ref:
        obs.append({
            "code": "low_attendance",
            "text": f"Attendance ({s['attendance_pct']:.1f}%) is below the reference level of {att_ref:g}%.",
            "severity": "high" if s["attendance_pct"] < att_ref - 10 else "medium",
        })
    if s.get("assignment_completion_pct") is not None and s["assignment_completion_pct"] < asg_ref:
        obs.append({
            "code": "low_assignments",
            "text": f"Assignment completion ({s['assignment_completion_pct']:.0f}%) is below the reference level of {asg_ref:g}%.",
            "severity": "high" if s["assignment_completion_pct"] < asg_ref - 20 else "medium",
        })
    scores = [v for v in (s.get("quiz_score"), s.get("test_score")) if v is not None]
    if scores and (sum(scores) / len(scores)) < score_ref:
        obs.append({
            "code": "low_scores",
            "text": f"Average quiz/test score ({sum(scores) / len(scores):.0f}%) is below the reference level of {score_ref:g}%.",
            "severity": "high",
        })
    trend = compute_score_trend(quiz_scores)
    if trend is not None and trend <= -5:
        obs.append({
            "code": "declining_scores",
            "text": f"Recent assessment scores are declining (change of {trend:+.1f} points across recorded assessments).",
            "severity": "medium",
        })
    elif trend is not None and trend >= 5:
        obs.append({
            "code": "improving_scores",
            "text": f"Recent assessment scores are improving ({trend:+.1f} points across recorded assessments).",
            "severity": "positive",
        })
    if s.get("self_understanding") is not None and s["self_understanding"] <= 2:
        obs.append({
            "code": "low_understanding",
            "text": f"Self-reported understanding of concepts is low ({s['self_understanding']}/5).",
            "severity": "medium",
        })
    if s.get("study_hours") is not None and s["study_hours"] < hours_ref:
        obs.append({
            "code": "low_study_hours",
            "text": f"Average daily study time ({s['study_hours']:g} h) is below the reference of {hours_ref:g} h.",
            "severity": "low",
        })
    if s.get("participation") == "Low" or s.get("engagement_level") == "Low":
        obs.append({
            "code": "low_engagement",
            "text": "Class participation or engagement is rated Low.",
            "severity": "low",
        })
    if not obs:
        obs.append({
            "code": "no_concerns",
            "text": "All recorded indicators are at or above the configured reference levels.",
            "severity": "positive",
        })
    return obs


SUGGESTIONS = {
    "low_attendance": "Attend all upcoming lectures and labs; ask faculty about catching up on missed sessions.",
    "low_assignments": "Complete pending assignments first and submit them before the next deadline.",
    "low_scores": "Revise the topics covered in recent quizzes and tests; practise previous question papers.",
    "declining_scores": "Review your most recent assessments to identify where marks were lost and seek help on those topics.",
    "low_understanding": "Book a doubt-clearing session with your faculty mentor for the concepts you find difficult.",
    "low_study_hours": "Plan a regular daily study schedule of at least two hours and stick to it for the next two weeks.",
    "low_engagement": "Participate actively in class: ask questions and join study groups or tutorials.",
    "no_concerns": "Keep up the consistent effort and maintain your attendance and submission record.",
    "improving_scores": "Your recent scores are improving; keep following the same study routine.",
}


def build_suggestions(observations: list[dict]) -> list[str]:
    out = []
    for o in observations:
        text = SUGGESTIONS.get(o["code"])
        if text and text not in out:
            out.append(text)
    if len(out) == 0:
        out.append(SUGGESTIONS["no_concerns"])
    return out
