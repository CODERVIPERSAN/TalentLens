"""
Per-candidate reasoning from real profile signals — no LLM, no network.

Tier depth (by rank):
  1–10  : full — why this rank, top strengths, exact gaps vs senior JD
  11–50 : medium — key fit + primary limitation
  51–100: concise — one strength + one reason not higher
"""

from __future__ import annotations

from typing import Any

from app.services.rank_features import has_career_ir_proof

CAREER_IR = {
    "ranking", "retrieval", "recommendation", "search", "embedding", "vector",
    "semantic", "rag", "nlp", "fine-tun", "ndcg", "recsys", "re-rank", "learning to rank",
}

IR_SKILL_TERMS = ("python", "embed", "retriev", "rank", "llm", "vector", "faiss", "nlp", "rag", "ndcg", "faiss", "pinecone")

FLAG_REASONS: dict[str, str] = {
    "LONG_NOTICE_PERIOD": "notice period exceeds JD preference (sub-30 days ideal)",
    "LOW_RESPONSE_RATE": "low recruiter response rate — likely harder to engage for outreach",
    "JUNIOR_TITLE_FOR_SENIOR_ROLE": "current title is Junior-level; JD targets Senior founding engineer",
    "NON_INDIA_LOCATION": "based outside India while role is Pune/Noida-first",
    "SERVICES_EMPLOYER_CURRENT": "currently at a services/consulting employer vs product-company mandate",
    "EXPERIENCE_BELOW_BAND": "years of experience below the 5–9 yr sweet spot",
    "EXPERIENCE_ABOVE_BAND": "experience well above the 5–9 yr band the JD centers on",
    "SKILLS_WITHOUT_CAREER_PROOF": "skills list AI/IR buzzwords but career history lacks matching project evidence",
    "KEYWORD_STUFFER_TRAP": "skills-heavy profile with wrong title — keyword-stuffer pattern",
    "LOW_ENGAGEMENT": "weak platform engagement signals (activity, completeness, or response patterns)",
    "CONSULTING_HEAVY": "career skewed toward consulting/services firms",
    "TITLE_CHASER_PATTERN": "many short stints — title-chaser risk for a 3+ year founding role",
    "GHOST_UNAVAILABLE": "inactive on platform with very low response — not hireable right now",
}


def _career_proof_snippet(candidate: dict[str, Any]) -> str | None:
    for job in candidate.get("career_history", []):
        combined = f"{job.get('title', '')} {job.get('description', '')}".lower()
        for kw in CAREER_IR:
            if kw in combined:
                company = job.get("company", "prior role")
                title = job.get("title", "engineer")
                return f"career proof: {title} at {company} involved {kw}"
    return None


def _top_verified_skills(candidate: dict[str, Any], limit: int = 3) -> list[str]:
    out: list[str] = []
    for skill in candidate.get("skills", []):
        name = skill.get("name", "")
        if not name:
            continue
        low = name.lower()
        if not any(t in low for t in IR_SKILL_TERMS):
            continue
        endorsements = skill.get("endorsements", 0)
        duration = skill.get("duration_months", 0)
        prof = skill.get("proficiency", "")
        if endorsements > 30 and duration < 6:
            continue
        if prof in ("advanced", "expert") or duration >= 12:
            out.append(name)
        elif len(out) < limit:
            out.append(name)
        if len(out) >= limit:
            break
    return out


def _stuffed_skill_note(candidate: dict[str, Any]) -> str | None:
    for skill in candidate.get("skills", []):
        if skill.get("endorsements", 0) > 30 and skill.get("duration_months", 0) < 6:
            return (
                f'"{skill.get("name")}" looks endorsement-stuffed '
                f'({skill.get("endorsements")} endorsements in {skill.get("duration_months")}mo) — skills discounted'
            )
    return None


def _strengths(candidate: dict[str, Any], breakdown: dict[str, float]) -> list[str]:
    profile = candidate.get("profile", {})
    signals = candidate.get("redrob_signals", {})
    strengths: list[str] = []

    title = profile.get("current_title", "")
    company = profile.get("current_company", "")
    if breakdown.get("title", 0) >= 0.85:
        strengths.append(f"strong title match ({title} at {company})")
    elif breakdown.get("title", 0) >= 0.70:
        strengths.append(f"relevant ML/engineering title ({title} at {company})")

    snippet = _career_proof_snippet(candidate)
    if snippet:
        strengths.append(snippet)
    elif breakdown.get("career", 0) >= 0.35:
        strengths.append("career history shows production ML/search work")

    verified = _top_verified_skills(candidate)
    if verified:
        strengths.append(f"verified skills: {', '.join(verified)}")

    years = profile.get("years_of_experience", 0)
    if 5 <= years <= 9:
        strengths.append(f"{years:.1f} yrs exp in JD sweet spot (5–9)")

    loc = profile.get("location", "")
    if breakdown.get("location", 0) >= 0.95:
        strengths.append(f"India-based ({loc}) — location fit for Pune/Noida")

    rr = signals.get("recruiter_response_rate")
    if isinstance(rr, (int, float)) and rr >= 0.55:
        strengths.append(f"healthy response rate ({rr:.0%}) — actively engageable")

    notice = signals.get("notice_period_days")
    if isinstance(notice, int) and notice <= 30:
        strengths.append(f"notice {notice}d — can join quickly")

    if signals.get("open_to_work_flag"):
        strengths.append("open to work on platform")

    return strengths[:4]


def _weaknesses(
    candidate: dict[str, Any],
    breakdown: dict[str, float],
    audit: dict[str, Any],
) -> list[str]:
    profile = candidate.get("profile", {})
    signals = candidate.get("redrob_signals", {})
    weaknesses: list[str] = []

    for flag in audit.get("audit_flags", []):
        if flag in FLAG_REASONS:
            weaknesses.append(FLAG_REASONS[flag])

    stuffed = _stuffed_skill_note(candidate)
    if stuffed:
        weaknesses.append(stuffed)

    if breakdown.get("skills", 0) >= 0.55 and breakdown.get("career", 0) < 0.28 and not has_career_ir_proof(candidate):
        weaknesses.append("many AI keywords listed but no retrieval/ranking projects in career history")

    if breakdown.get("skills", 0) < 0.35 and breakdown.get("career", 0) >= 0.35:
        weaknesses.append("strong career proof but thin explicit IR skill list (Tier-5 profile — still valued)")

    rr = signals.get("recruiter_response_rate")
    if isinstance(rr, (int, float)) and 0.35 <= rr < 0.55 and "LOW_RESPONSE_RATE" not in audit.get("audit_flags", []):
        weaknesses.append(f"moderate response rate ({rr:.0%}) — below top cohort engagers")

    notice = signals.get("notice_period_days")
    if isinstance(notice, int) and 60 < notice <= 90:
        weaknesses.append(f"notice {notice}d — slower than JD's sub-30d preference")

    years = profile.get("years_of_experience", 0)
    if 4 <= years < 5 and "EXPERIENCE_BELOW_BAND" not in audit.get("audit_flags", []):
        weaknesses.append(f"{years:.1f} yrs — slightly below senior band but otherwise strong")

    if breakdown.get("behavioral", 1) < 0.78 and not weaknesses:
        weaknesses.append("behavioral signals (activity/engagement) weaker than candidates ranked above")

    if breakdown.get("jd_fit", 1) < 0.85 and not weaknesses:
        weaknesses.append("minor JD fit gaps on location, employer type, or seniority vs ranks above")

    return weaknesses[:3]


def _rank_framing(rank: int, tier: str, n_strengths: int, n_weak: int) -> str:
    if rank == 1:
        return "Rank #1: best overall match for Senior AI Engineer — "
    if rank <= 3:
        return f"Rank #{rank}: elite fit, only minor gaps vs #{rank - 1} — "
    if rank <= 10:
        return f"Rank #{rank}: top-10 founding-team fit ({tier}); ranked here because "
    if rank <= 30:
        return f"Rank #{rank}: strong candidate ({tier}) but below top-10 because "
    if rank <= 50:
        return f"Rank #{rank}: solid top-50 ({tier}); not higher because "
    return f"Rank #{rank}: in top-100 ({tier}) but ranked lower because "


def build_reasoning(
    candidate: dict[str, Any],
    breakdown: dict[str, float],
    audit: dict[str, Any],
    rank: int,
) -> str:
    profile = candidate.get("profile", {})
    tier = audit.get("fit_tier", "Good Fit")
    strengths = _strengths(candidate, breakdown)
    weaknesses = _weaknesses(candidate, breakdown, audit)

    if rank <= 10:
        intro = _rank_framing(rank, tier, len(strengths), len(weaknesses))
        parts = [intro]
        if strengths:
            parts.append("Strengths: " + "; ".join(strengths) + ".")
        if weaknesses:
            parts.append("Why not higher: " + "; ".join(weaknesses) + ".")
        elif rank > 1:
            parts.append("Why not higher: narrowly beaten on combined title+career+engagement vs ranks above.")
        else:
            parts.append("Clear leader on title, career IR proof, product employer, and engagement.")
        return " ".join(parts)

    if rank <= 50:
        intro = _rank_framing(rank, tier, len(strengths), len(weaknesses))
        main_strength = strengths[0] if strengths else f"{profile.get('current_title')} at {profile.get('current_company')}"
        main_weak = weaknesses[0] if weaknesses else "overall score trails top-30 on career depth or seniority signals"
        return f"{intro}{main_strength}. Primary gap: {main_weak}."

    # 51–100
    title = profile.get("current_title", "Engineer")
    company = profile.get("current_company", "N/A")
    s = strengths[0] if strengths else f"{title} at {company}"
    w = weaknesses[0] if weaknesses else "weaker combined ranking/retrieval career proof vs top half"
    return f"Rank #{rank}: {s}. Held back: {w}."


def estimate_llm_time_seconds(n_candidates: int, seconds_per_call: float = 3.0) -> float:
    """Rough estimate — LLM API is NOT allowed during challenge ranking."""
    return n_candidates * seconds_per_call
