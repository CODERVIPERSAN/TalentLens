"""
Cross-check auditor for ranked candidates.

Validates consistency between title, skills, career, and behavioral signals.
Produces confidence scores and flags traps/honeypots before submission.
"""

from __future__ import annotations

from typing import Any


FIT_STRONG = "Strong Fit"
FIT_GOOD = "Good Fit"
FIT_BORDERLINE = "Borderline"
FIT_CONCERN = "Concern"


def cross_check_candidate(candidate: dict[str, Any], breakdown: dict[str, float]) -> dict[str, Any]:
    """Run consistency checks and return audit metadata."""
    flags: list[str] = []
    profile = candidate.get("profile", {})
    signals = candidate.get("redrob_signals", {})
    skills = {s.get("name", "").lower() for s in candidate.get("skills", []) if s.get("name")}
    title = (profile.get("current_title") or "").lower()

    title_s = breakdown.get("title", 0.5)
    career_s = breakdown.get("career", 0.5)
    skills_s = breakdown.get("skills", 0.5)
    penalties = breakdown.get("penalties", 1.0)
    behavioral = breakdown.get("behavioral", 1.0)
    final_s = breakdown.get("final", 0.5)

    # Trap: many AI skills but wrong title (challenge keyword stuffer)
    if skills_s >= 0.65 and title_s <= 0.25:
        flags.append("KEYWORD_STUFFER_TRAP")

    # Trap: skills listed but no career proof
    if skills_s >= 0.55 and career_s < 0.2:
        flags.append("SKILLS_WITHOUT_CAREER_PROOF")

    # Trap: consulting-only background
    if penalties < 0.75 and penalties >= 0.4:
        flags.append("CONSULTING_HEAVY")

    # Honeypot suspect
    if penalties <= 0.1:
        flags.append("HONEYPOT_SUSPECT")

    # Inactive / unavailable
    if behavioral < 0.75:
        flags.append("LOW_ENGAGEMENT")

    # CV-only without IR
    if penalties < 0.55 and penalties > 0.1:
        ai_skill_count = sum(
            1 for s in skills
            if any(k in s for k in ("nlp", "llm", "rag", "retriev", "rank", "embed"))
        )
        cv_count = sum(1 for s in skills if any(k in s for k in ("vision", "speech", "robot")))
        if cv_count >= 2 and ai_skill_count == 0:
            flags.append("CV_ONLY_PROFILE")

    # Title-chaser: many short stints
    history = candidate.get("career_history", [])
    if len(history) >= 4:
        short_stints = sum(1 for j in history if j.get("duration_months", 0) < 18)
        if short_stints >= len(history) * 0.6:
            flags.append("TITLE_CHASER_PATTERN")

    # Notice period concern
    notice = signals.get("notice_period_days", 0)
    if notice > 90:
        flags.append("LONG_NOTICE_PERIOD")

    # Confidence: agreement between independent signals
    core_signals = [title_s, career_s, skills_s]
    signal_mean = sum(core_signals) / len(core_signals)
    signal_spread = max(core_signals) - min(core_signals)
    agreement = max(0.0, 1.0 - signal_spread)
    confidence = round(
        (agreement * 0.35 + signal_mean * 0.35 + min(final_s, 1.0) * 0.20 + min(behavioral, 1.2) * 0.10) * 100,
        1,
    )
    if flags:
        confidence = round(confidence * (1.0 - 0.08 * min(len(flags), 4)), 1)

    fit_tier = _fit_tier(confidence, final_s, flags)

    return {
        "confidence": confidence,
        "fit_tier": fit_tier,
        "audit_flags": flags,
        "cross_check_score": round(agreement, 3),
        "signal_agreement": round(agreement, 3),
    }


def _fit_tier(confidence: float, final_score: float, flags: list[str]) -> str:
    if "HONEYPOT_SUSPECT" in flags or "KEYWORD_STUFFER_TRAP" in flags:
        return FIT_CONCERN
    if confidence >= 78 and final_score >= 0.55 and len(flags) <= 1:
        return FIT_STRONG
    if confidence >= 58 and final_score >= 0.4:
        return FIT_GOOD
    if confidence >= 38:
        return FIT_BORDERLINE
    return FIT_CONCERN


def audit_ranking(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Produce a quality report for the full ranking."""
    if not results:
        return {"quality_score": 0, "honeypot_rate": 0, "flags_summary": {}}

    flag_counts: dict[str, int] = {}
    honeypots = 0
    strong = 0
    concerns = 0
    confidences: list[float] = []

    for r in results:
        audit = r.get("audit", {})
        for flag in audit.get("audit_flags", []):
            flag_counts[flag] = flag_counts.get(flag, 0) + 1
            if flag == "HONEYPOT_SUSPECT":
                honeypots += 1
        tier = audit.get("fit_tier", "")
        if tier == FIT_STRONG:
            strong += 1
        elif tier == FIT_CONCERN:
            concerns += 1
        confidences.append(audit.get("confidence", 0))

    n = len(results)
    honeypot_rate = round(honeypots / n, 4)
    avg_confidence = round(sum(confidences) / n, 1) if confidences else 0

    # Quality score 0-100 for hackathon self-assessment
    quality = 100.0
    quality -= honeypot_rate * 500  # >10% honeypot = disqualify
    quality -= concerns / n * 30
    quality += strong / n * 15
    quality += avg_confidence * 0.2
    quality = round(max(0, min(100, quality)), 1)

    submission_ready = honeypot_rate <= 0.10 and concerns <= n * 0.15

    return {
        "quality_score": quality,
        "avg_confidence": avg_confidence,
        "strong_fit_count": strong,
        "concern_count": concerns,
        "honeypot_count": honeypots,
        "honeypot_rate": honeypot_rate,
        "honeypot_safe": honeypot_rate <= 0.10,
        "submission_ready": submission_ready,
        "flags_summary": flag_counts,
        "recommendation": _recommendation(quality, honeypot_rate, submission_ready),
    }


def _recommendation(quality: float, honeypot_rate: float, ready: bool) -> str:
    if honeypot_rate > 0.10:
        return "BLOCKED: Honeypot rate exceeds 10% — re-rank with stricter filters before submitting."
    if not ready:
        return "REVIEW: Run audit and remove Concern-tier candidates from top ranks."
    if quality >= 85:
        return "EXCELLENT: High-confidence ranking ready for submission."
    if quality >= 70:
        return "GOOD: Solid ranking — review Borderline matches in top 20."
    return "IMPROVE: Too many low-confidence matches — tune ranker weights."
