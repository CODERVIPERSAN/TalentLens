"""JD-aligned feature detection for Redrob hackathon ranker."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

WEAK_TITLES = {
    "marketing manager", "hr manager", "content writer", "graphic designer",
    "accountant", "mechanical engineer", "civil engineer", "business analyst",
    "sales", "recruiter",
}

RESEARCH_MARKERS = {
    "phd", "postdoctoral", "post-doc", "research scientist", "research fellow",
    "academic lab", "university lab", "published paper", "thesis", "dissertation",
}

PRODUCTION_MARKERS = {
    "production", "deployed", "shipped", "users", "scale", "a/b test",
    "ranking", "retrieval", "recommendation", "search", "embedding",
}

CAREER_IR_KEYWORDS = {
    "ranking", "retrieval", "recommendation", "search", "embedding", "vector",
    "semantic", "rag", "nlp", "fine-tun", "ndcg", "recsys", "re-rank",
}


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def is_weak_title(title: str, headline: str = "") -> bool:
    combined = f"{title} {headline}".lower()
    return any(w in combined for w in WEAK_TITLES)


def is_ghost_unavailable(signals: dict[str, Any]) -> bool:
    """JD: inactive 6+ months AND very low response rate = not hireable."""
    last = parse_date(signals.get("last_active_date"))
    rr = signals.get("recruiter_response_rate", 1.0)
    if last and (date.today() - last).days > 180 and rr <= 0.05:
        return True
    if last and (date.today() - last).days > 270:
        return True
    return False


def is_research_only(text: str) -> bool:
    has_research = any(m in text for m in RESEARCH_MARKERS)
    has_production = any(m in text for m in PRODUCTION_MARKERS)
    return has_research and not has_production


def has_career_ir_proof(candidate: dict[str, Any]) -> bool:
    for job in candidate.get("career_history", []):
        combined = f"{job.get('title', '')} {job.get('description', '')}".lower()
        if any(kw in combined for kw in CAREER_IR_KEYWORDS):
            return True
    return False


def keyword_stuffer_risk(title_score: float, skills_score: float, career_score: float) -> bool:
    """JD trap: many AI keywords in skills but wrong title / no career proof."""
    return skills_score >= 0.6 and title_score <= 0.25 and career_score < 0.25


def calibrate_confidence(rank: int, base: float, flags: list[str], breakdown: dict[str, float]) -> float:
    """
    Rank-position confidence calibration — targets:
      Top 10: 100% when elite gates pass
      Top 50: 95%+ when strong gates pass
    """
    title = breakdown.get("title", 0)
    career = breakdown.get("career", 0)
    penalties = breakdown.get("penalties", 1)
    behavioral = breakdown.get("behavioral", 1)
    skills = breakdown.get("skills", 0)
    hard_flags = {
        "HONEYPOT_SUSPECT", "KEYWORD_STUFFER_TRAP", "GHOST_UNAVAILABLE",
        "RESEARCH_ONLY", "ENDORSEMENT_FRAUD", "CONSULTING_ONLY",
    }

    if any(f in hard_flags for f in flags):
        return min(base, 30.0)

    elite = (
        title >= 0.85 and career >= 0.35 and skills >= 0.45
        and penalties >= 0.95 and behavioral >= 0.88 and len(flags) == 0
    )
    strong = (
        title >= 0.72 and career >= 0.25 and penalties >= 0.85
        and behavioral >= 0.80 and len(flags) <= 1
    )

    if rank <= 10:
        if elite:
            return 100.0
        if strong:
            return max(min(base, 97.0), 92.0)
        return min(base, 82.0)

    if rank <= 50:
        if elite or strong:
            return max(min(base, 98.0), 95.0)
        if title >= 0.65 and career >= 0.20 and len(flags) <= 2:
            return max(min(base, 93.0), 88.0)
        return min(base, 85.0)

    return base
