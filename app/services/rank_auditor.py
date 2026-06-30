"""
Cross-check auditor — validates JD compliance per hackathon rules.
"""

from __future__ import annotations

from typing import Any

from app.services.fraud_detector import fraud_flags as detector_flags
from app.services.rank_features import (
    calibrate_confidence,
    has_career_ir_proof,
    is_ghost_unavailable,
    is_research_only,
    is_weak_title,
    keyword_stuffer_risk,
)

FIT_STRONG = "Strong Fit"
FIT_GOOD = "Good Fit"
FIT_BORDERLINE = "Borderline"
FIT_CONCERN = "Concern"


def cross_check_candidate(
    candidate: dict[str, Any],
    breakdown: dict[str, float],
    rank: int | None = None,
) -> dict[str, Any]:
    flags: list[str] = []
    profile = candidate.get("profile", {})
    signals = candidate.get("redrob_signals", {})
    skills = {s.get("name", "").lower() for s in candidate.get("skills", []) if s.get("name")}
    title = profile.get("current_title", "")

    title_s = breakdown.get("title", 0.5)
    career_s = breakdown.get("career", 0.5)
    skills_s = breakdown.get("skills", 0.5)
    penalties = breakdown.get("penalties", 1.0)
    behavioral = breakdown.get("behavioral", 1.0)
    final_s = breakdown.get("final", 0.5)

    text = _brief_text(candidate)

    # JD hackathon traps
    if keyword_stuffer_risk(title_s, skills_s, career_s) or is_weak_title(title, profile.get("headline", "")):
        if skills_s >= 0.55 and title_s <= 0.25:
            flags.append("KEYWORD_STUFFER_TRAP")

    if skills_s >= 0.55 and career_s < 0.2 and not has_career_ir_proof(candidate):
        flags.append("SKILLS_WITHOUT_CAREER_PROOF")

    if is_ghost_unavailable(signals):
        flags.append("GHOST_UNAVAILABLE")

    for ff in detector_flags(candidate):
        if ff not in flags:
            flags.append(ff)

    if is_research_only(text):
        flags.append("RESEARCH_ONLY")

    if penalties < 0.75 and penalties >= 0.4:
        flags.append("CONSULTING_HEAVY")

    if penalties <= 0.1:
        flags.append("HONEYPOT_SUSPECT")

    if behavioral < 0.72:
        flags.append("LOW_ENGAGEMENT")

    cv_count = sum(1 for s in skills if any(k in s for k in ("vision", "speech", "robot")))
    ir_count = sum(1 for s in skills if any(k in s for k in ("nlp", "retriev", "rank", "embed", "llm", "rag")))
    if cv_count >= 2 and ir_count == 0 and not has_career_ir_proof(candidate):
        flags.append("CV_ONLY_PROFILE")

    history = candidate.get("career_history", [])
    if len(history) >= 4:
        short = sum(1 for j in history if j.get("duration_months", 0) < 18)
        if short >= len(history) * 0.6:
            flags.append("TITLE_CHASER_PATTERN")

    if signals.get("notice_period_days", 0) > 90:
        flags.append("LONG_NOTICE_PERIOD")

    core_signals = [title_s, career_s, skills_s]
    signal_mean = sum(core_signals) / 3
    agreement = max(0.0, 1.0 - (max(core_signals) - min(core_signals)))
    base_conf = (agreement * 0.35 + signal_mean * 0.35 + min(final_s, 1.0) * 0.20 + min(behavioral, 1.2) * 0.10) * 100
    if flags:
        base_conf *= 1.0 - 0.07 * min(len(flags), 5)

    confidence = round(base_conf, 1)
    if rank is not None:
        confidence = calibrate_confidence(rank, confidence, flags, breakdown)

    fit_tier = _fit_tier(confidence, final_s, flags, rank)

    return {
        "confidence": confidence,
        "fit_tier": fit_tier,
        "audit_flags": flags,
        "cross_check_score": round(agreement, 3),
        "signal_agreement": round(agreement, 3),
        "career_ir_proof": has_career_ir_proof(candidate),
    }


def _brief_text(candidate: dict[str, Any]) -> str:
    parts = []
    p = candidate.get("profile", {})
    parts.extend([p.get("summary", ""), p.get("headline", "")])
    for j in candidate.get("career_history", []):
        parts.append(j.get("description", ""))
    return " ".join(parts).lower()


def _fit_tier(confidence: float, final_score: float, flags: list[str], rank: int | None) -> str:
    hard = {"HONEYPOT_SUSPECT", "KEYWORD_STUFFER_TRAP", "GHOST_UNAVAILABLE"}
    if any(f in hard for f in flags):
        return FIT_CONCERN
    if rank is not None and rank <= 10 and confidence >= 95 and len(flags) == 0:
        return FIT_STRONG
    if confidence >= 78 and final_score >= 0.55 and len(flags) <= 1:
        return FIT_STRONG
    if confidence >= 58 and final_score >= 0.4:
        return FIT_GOOD
    if confidence >= 38:
        return FIT_BORDERLINE
    return FIT_CONCERN


def audit_ranking(results: list[dict[str, Any]]) -> dict[str, Any]:
    if not results:
        return {"quality_score": 0, "honeypot_rate": 0, "flags_summary": {}}

    flag_counts: dict[str, int] = {}
    honeypots = ghosts = strong = concerns = 0
    confidences: list[float] = []
    top10_conf: list[float] = []
    top50_conf: list[float] = []

    for r in results:
        audit = r.get("audit", {})
        rank = r.get("rank", 999)
        for flag in audit.get("audit_flags", []):
            flag_counts[flag] = flag_counts.get(flag, 0) + 1
            if flag == "HONEYPOT_SUSPECT":
                honeypots += 1
            if flag == "GHOST_UNAVAILABLE":
                ghosts += 1
        tier = audit.get("fit_tier", "")
        if tier == FIT_STRONG:
            strong += 1
        elif tier == FIT_CONCERN:
            concerns += 1
        c = audit.get("confidence", 0)
        confidences.append(c)
        if rank <= 10:
            top10_conf.append(c)
        if rank <= 50:
            top50_conf.append(c)

    n = len(results)
    honeypot_rate = round(honeypots / n, 4)

    report = {
        "quality_score": _quality_score(n, honeypot_rate, strong, concerns, confidences),
        "avg_confidence": round(sum(confidences) / n, 1) if confidences else 0,
        "top10_avg_confidence": round(sum(top10_conf) / len(top10_conf), 1) if top10_conf else 0,
        "top50_avg_confidence": round(sum(top50_conf) / len(top50_conf), 1) if top50_conf else 0,
        "top10_target_met": all(c >= 98 for c in top10_conf) if top10_conf else False,
        "top50_target_met": all(c >= 95 for c in top50_conf) if top50_conf else False,
        "strong_fit_count": strong,
        "concern_count": concerns,
        "honeypot_count": honeypots,
        "ghost_count": ghosts,
        "honeypot_rate": honeypot_rate,
        "honeypot_safe": honeypot_rate <= 0.10,
        "submission_ready": honeypot_rate <= 0.10 and concerns <= n * 0.12,
        "flags_summary": flag_counts,
    }
    report["recommendation"] = _recommendation(report)
    return report


def _quality_score(n: int, honeypot_rate: float, strong: int, concerns: int, confidences: list[float]) -> float:
    q = 100.0
    q -= honeypot_rate * 500
    q -= concerns / n * 30
    q += strong / n * 15
    q += (sum(confidences) / n if confidences else 0) * 0.2
    return round(max(0, min(100, q)), 1)


def _recommendation(report: dict[str, Any]) -> str:
    if report["honeypot_rate"] > 0.10:
        return "BLOCKED: Honeypot rate >10% in top-100 — disqualifies submission."
    if report.get("ghost_count", 0) > 5:
        return "WARNING: Too many ghost/inactive candidates in top ranks."
    if report.get("top10_target_met") and report.get("submission_ready"):
        return "EXCELLENT: Top-10 at 100% confidence. Ready for submission."
    if report.get("submission_ready"):
        return "GOOD: Honeypot-safe. Review top-10 confidence before submitting."
    return "REVIEW: Demote Concern-tier and trap-flagged candidates from top ranks."
