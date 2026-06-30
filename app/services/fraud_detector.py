"""
Fraud / honeypot / ghost detection per PUB challenge + JD rules.

Honeypots (~80 in pool): impossible timelines, notice >180d, endorsement fraud.
Ghosts: inactive 6+ months + ≤5% recruiter response (JD explicit).
Keyword traps: AI skills + wrong title (Marketing Manager, etc.).
"""

from __future__ import annotations

import math
from typing import Any

from app.services.rank_features import is_ghost_unavailable, is_weak_title, parse_date

CV_ONLY = {"computer vision", "object detection", "speech", "robotics", "autonomous"}
CONSULTING = {
    "tcs", "infosys", "wipro", "accenture", "cognizant", "capgemini", "mindtree",
    "hcl", "tech mahindra", "ltimindtree", "mphasis", "persistent", "lti",
}


def endorsement_fraud_count(skills: list[dict[str, Any]]) -> int:
    return sum(
        1 for s in skills
        if s.get("endorsements", 0) > 30 and s.get("duration_months", 0) < 6
    )


def is_honeypot(candidate: dict[str, Any]) -> bool:
    profile = candidate.get("profile", {})
    signals = candidate.get("redrob_signals", {})
    years = profile.get("years_of_experience", 0)
    months = sum(j.get("duration_months", 0) for j in candidate.get("career_history", []))

    if years > 0 and months > 0:
        exp = years * 12
        if months > exp * 2.5 or months < exp * 0.25:
            return True

    if signals.get("notice_period_days", 0) > 180:
        return True

    if endorsement_fraud_count(candidate.get("skills", [])) >= 4:
        return True

    years_exp = profile.get("years_of_experience", 0)
    if years_exp >= 12 and len(candidate.get("career_history", [])) == 1:
        desc = candidate.get("career_history", [{}])[0].get("description", "")
        if len(desc) < 80:
            return True

    return False


def is_keyword_trap(candidate: dict[str, Any]) -> bool:
    profile = candidate.get("profile", {})
    title = profile.get("current_title", "")
    headline = profile.get("headline", "")
    if not is_weak_title(title, headline):
        return False
    skills = candidate.get("skills", [])
    ai_kw = sum(
        1 for s in skills
        if any(k in s.get("name", "").lower() for k in ("llm", "rag", "embed", "pinecone", "langchain", "vector", "openai"))
    )
    return ai_kw >= 4


def is_consulting_only(candidate: dict[str, Any]) -> bool:
    companies = [candidate.get("profile", {}).get("current_company", "").lower()]
    companies.extend(j.get("company", "").lower() for j in candidate.get("career_history", []))
    if not companies:
        return False
    hits = sum(1 for c in companies if any(f in c for f in CONSULTING))
    return hits == len(companies)


def is_cv_only_no_nlp(candidate: dict[str, Any]) -> bool:
    skills = {s.get("name", "").lower() for s in candidate.get("skills", []) if s.get("name")}
    cv = sum(1 for s in skills if any(c in s for c in CV_ONLY))
    ir = sum(1 for s in skills if any(k in s for k in ("nlp", "retriev", "rank", "embed", "llm", "rag", "search")))
    if cv >= 2 and ir == 0:
        text = " ".join(
            j.get("description", "") for j in candidate.get("career_history", [])
        ).lower()
        if not any(k in text for k in ("nlp", "retriev", "rank", "embed", "search", "recommend")):
            return True
    return False


def fraud_penalty(candidate: dict[str, Any]) -> float:
    """Multiplicative penalty 0.01–1.0."""
    if is_honeypot(candidate):
        return 0.02
    if is_ghost_unavailable(candidate.get("redrob_signals", {})):
        return 0.06
    if is_keyword_trap(candidate):
        return 0.08
    p = 1.0
    if is_consulting_only(candidate):
        p *= 0.42
    if is_cv_only_no_nlp(candidate):
        p *= 0.38
    if endorsement_fraud_count(candidate.get("skills", [])) >= 3:
        p *= 0.55
    signals = candidate.get("redrob_signals", {})
    last = parse_date(signals.get("last_active_date"))
    if last:
        from datetime import date
        days = (date.today() - last).days
        if days > 120 and signals.get("recruiter_response_rate", 1) < 0.12:
            p *= 0.65
    return p


def fraud_flags(candidate: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    if is_honeypot(candidate):
        flags.append("HONEYPOT_SUSPECT")
    if is_ghost_unavailable(candidate.get("redrob_signals", {})):
        flags.append("GHOST_UNAVAILABLE")
    if is_keyword_trap(candidate):
        flags.append("KEYWORD_STUFFER_TRAP")
    if is_consulting_only(candidate):
        flags.append("CONSULTING_ONLY")
    if is_cv_only_no_nlp(candidate):
        flags.append("CV_ONLY_PROFILE")
    if endorsement_fraud_count(candidate.get("skills", [])) >= 3:
        flags.append("ENDORSEMENT_FRAUD")
    return flags


def fraud_risk_score(candidate: dict[str, Any]) -> float:
    """0 = clean, 1 = definite fraud."""
    risk = 0.0
    if is_honeypot(candidate):
        return 1.0
    if is_ghost_unavailable(candidate.get("redrob_signals", {})):
        risk += 0.45
    if is_keyword_trap(candidate):
        risk += 0.40
    if is_consulting_only(candidate):
        risk += 0.25
    if endorsement_fraud_count(candidate.get("skills", [])) >= 3:
        risk += 0.20
    return min(risk, 1.0)
