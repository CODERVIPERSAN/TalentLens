"""
TalentLens Pro Ranker — two-stage CPU-only engine for Redrob hackathon.

Stage 1 (Recall): Fast TF-IDF + title filter on full pool (100K in ~30s)
Stage 2 (Precision): Deep multi-signal scoring on top finalists
Stage 3 (Audit): Cross-check, confidence, honeypot scan via rank_auditor.py

No network calls. Designed to beat keyword-stuffing traps.
"""

from __future__ import annotations

import csv
import gzip
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.services.rank_auditor import cross_check_candidate

# ── JD-aligned skill & title lexicons ──────────────────────────────────────

CORE_SKILLS = {
    "python", "embeddings", "retrieval", "ranking", "vector search", "faiss",
    "elasticsearch", "opensearch", "pinecone", "weaviate", "qdrant", "milvus",
    "sentence-transformers", "bge", "e5", "ndcg", "mrr", "map", "learning to rank",
    "llm", "fine-tuning", "lora", "qlora", "rag", "nlp", "information retrieval",
    "semantic search", "hybrid search", "recommendation", "a/b testing",
    "pytorch", "tensorflow", "xgboost", "machine learning", "deep learning",
}

STRONG_TITLES = {
    "ai engineer", "ml engineer", "machine learning engineer", "applied scientist",
    "search engineer", "recommendation engineer", "data scientist", "staff engineer",
    "senior engineer", "principal engineer", "research engineer",
}

WEAK_TITLES = {
    "marketing manager", "hr manager", "content writer", "graphic designer",
    "accountant", "mechanical engineer", "civil engineer", "business analyst",
    "sales", "recruiter",
}

CONSULTING_FIRMS = {
    "tcs", "infosys", "wipro", "accenture", "cognizant", "capgemini", "mindtree",
    "hcl", "tech mahindra", "ltimindtree", "mphasis", "persistent", "lti",
}

PRODUCT_COMPANIES = {
    "swiggy", "zomato", "razorpay", "flipkart", "amazon", "google", "microsoft",
    "meta", "uber", "ola", "phonepe", "paytm", "freshworks", "zoho", "cred",
    "meesho", "sharechat", "dream11", "redrob", "unacademy", "byju",
}

INDIA_LOCATIONS = {
    "bangalore", "bengaluru", "pune", "noida", "delhi", "gurgaon", "gurugram",
    "hyderabad", "mumbai", "chennai", "india",
}

CV_ONLY_SKILLS = {
    "computer vision", "object detection", "image segmentation", "speech recognition",
    "robotics", "autonomous driving",
}

CAREER_IR_KEYWORDS = {
    "ranking", "retrieval", "recommendation", "search", "embedding", "vector",
    "semantic", "rag", "nlp", "ml model", "machine learning", "fine-tun",
    "a/b test", "ndcg", "recsys", "re-rank", "two-tower", "learning to rank",
}

PRODUCT_INDICATORS = {
    "product", "startup", "series", "saas", "platform", "scale", "users",
    "production", "deployed", "shipped", "a/b", "million users",
}

RECALL_TOP_K = 2500  # Stage-1 shortlist size for 100K pool


@dataclass
class RankedCandidate:
    candidate_id: str
    rank: int
    score: float
    reasoning: str
    profile_summary: dict[str, Any]
    score_breakdown: dict[str, float] = field(default_factory=dict)
    audit: dict[str, Any] = field(default_factory=dict)


def load_candidates(path: Path) -> list[dict[str, Any]]:
    suffixes = "".join(path.suffixes).lower()
    if suffixes == ".json":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else [data]
    opener = gzip.open(path, "rt", encoding="utf-8") if suffixes.endswith(".gz") else open(path, encoding="utf-8")
    with opener as f:
        return [json.loads(line) for line in f if line.strip()]


def _candidate_text(candidate: dict[str, Any]) -> str:
    parts: list[str] = []
    profile = candidate.get("profile", {})
    parts.extend([
        profile.get("headline", ""), profile.get("summary", ""),
        profile.get("current_title", ""), profile.get("current_company", ""),
        profile.get("current_industry", ""), profile.get("location", ""),
    ])
    for job in candidate.get("career_history", []):
        parts.extend([job.get("title", ""), job.get("company", ""), job.get("description", "")])
    for skill in candidate.get("skills", []):
        parts.append(skill.get("name", ""))
    for edu in candidate.get("education", []):
        parts.extend([edu.get("degree", ""), edu.get("field_of_study", ""), edu.get("institution", "")])
    return " ".join(p for p in parts if p).lower()


def _skill_names(candidate: dict[str, Any]) -> set[str]:
    return {s.get("name", "").lower() for s in candidate.get("skills", []) if s.get("name")}


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _fast_recall_score(candidate: dict[str, Any], semantic: float) -> float:
    """Stage-1 lightweight score for 100K recall."""
    profile = candidate.get("profile", {})
    title = _title_score(profile.get("current_title", ""), profile.get("headline", ""))
    hp = _honeypot_penalty(candidate)
    if hp < 0.2:
        return 0.0
    return title * 0.45 + semantic * 0.35 + _career_relevance_score(candidate) * 0.20


def _skill_trust_multiplier(candidate: dict[str, Any]) -> float:
    skills = candidate.get("skills", [])
    if not skills:
        return 0.5
    trusted = 0.0
    stuffed = 0
    for skill in skills:
        endorsements = skill.get("endorsements", 0)
        duration = skill.get("duration_months", 0)
        proficiency = skill.get("proficiency", "beginner")
        if endorsements > 30 and duration < 6:
            stuffed += 1
            continue
        if proficiency in ("advanced", "expert") and duration >= 12:
            trusted += 1.5
        elif proficiency in ("intermediate", "advanced"):
            trusted += 1.0
        else:
            trusted += 0.5
    trust = min(trusted / max(len(skills) - stuffed, 1), 1.0)
    if stuffed >= 3:
        trust *= 0.7
    return trust


def _assessment_boost(signals: dict[str, Any]) -> float:
    assessments = signals.get("skill_assessment_scores") or {}
    if not assessments:
        return 0.5
    relevant = [
        score / 100.0 for name, score in assessments.items()
        if any(c in name.lower() for c in ("python", "ml", "nlp", "retriev", "rank", "embed", "search"))
    ]
    return sum(relevant) / len(relevant) if relevant else 0.5


def _behavioral_multiplier(signals: dict[str, Any]) -> float:
    if not signals:
        return 0.7
    m = 1.0
    if signals.get("open_to_work_flag"):
        m *= 1.06
    rr = signals.get("recruiter_response_rate", 0)
    if rr >= 0.5:
        m *= 1.09
    elif rr < 0.15:
        m *= 0.80
    notice = signals.get("notice_period_days", 90)
    if notice <= 30:
        m *= 1.07
    elif notice > 90:
        m *= 0.88
    if signals.get("saved_by_recruiters_30d", 0) >= 3:
        m *= 1.05
    icr = signals.get("interview_completion_rate", 0)
    if icr >= 0.8:
        m *= 1.04
    elif icr < 0.3:
        m *= 0.87
    if signals.get("profile_views_received_30d", 0) >= 10:
        m *= 1.03
    m *= 0.88 + 0.12 * (signals.get("profile_completeness_score", 50) / 100.0)
    last = _parse_date(signals.get("last_active_date"))
    if last:
        days = (date.today() - last).days
        if days > 180:
            m *= 0.72
        elif days > 90:
            m *= 0.86
    gh = signals.get("github_activity_score", -1)
    if gh >= 50:
        m *= 1.05
    return min(max(m, 0.50), 1.28)


def _title_score(title: str, headline: str) -> float:
    combined = f"{title} {headline}".lower()
    for weak in WEAK_TITLES:
        if weak in combined:
            return 0.12
    for strong in STRONG_TITLES:
        if strong in combined:
            return 1.0
    if any(kw in combined for kw in ("engineer", "scientist", "architect")):
        return 0.72
    return 0.40


def _career_relevance_score(candidate: dict[str, Any]) -> float:
    ir_hits = product_hits = product_co = 0
    for job in candidate.get("career_history", []):
        combined = f"{job.get('title', '')} {job.get('description', '')}".lower()
        company = job.get("company", "").lower()
        if any(kw in combined for kw in CAREER_IR_KEYWORDS):
            ir_hits += 1
        if any(kw in combined for kw in PRODUCT_INDICATORS):
            product_hits += 1
        if any(pc in company for pc in PRODUCT_COMPANIES):
            product_co += 1
    n = max(len(candidate.get("career_history", [])), 1)
    return min(ir_hits / n * 0.45 + product_hits / n * 0.30 + product_co / n * 0.25, 1.0)


def _tenure_stability(candidate: dict[str, Any]) -> float:
    history = candidate.get("career_history", [])
    if len(history) < 2:
        return 0.8
    short = sum(1 for j in history if j.get("duration_months", 0) < 15)
    return max(0.4, 1.0 - short / len(history) * 0.5)


def _education_boost(candidate: dict[str, Any]) -> float:
    tiers = [e.get("tier", "unknown") for e in candidate.get("education", [])]
    if "tier_1" in tiers:
        return 1.0
    if "tier_2" in tiers:
        return 0.9
    return 0.75


def _experience_score(years: float) -> float:
    if 5 <= years <= 9:
        return 1.0
    if 4 <= years <= 12:
        return 0.85
    if 3 <= years <= 15:
        return 0.62
    return 0.30


def _location_score(location: str, country: str) -> float:
    loc = f"{location} {country}".lower()
    if any(c in loc for c in INDIA_LOCATIONS):
        return 1.0
    if country.lower() == "india":
        return 0.88
    return 0.40


def _consulting_penalty(candidate: dict[str, Any]) -> float:
    companies = [candidate.get("profile", {}).get("current_company", "").lower()]
    companies.extend(j.get("company", "").lower() for j in candidate.get("career_history", []))
    cc = sum(1 for c in companies if any(f in c for f in CONSULTING_FIRMS))
    n = max(len(companies), 1)
    if cc == n:
        return 0.45
    if cc > n * 0.6:
        return 0.68
    return 1.0


def _cv_only_penalty(skills: set[str], text: str) -> float:
    cv = sum(1 for s in skills if any(c in s for c in CV_ONLY_SKILLS))
    ir = sum(1 for s in skills if any(k in s for k in ("nlp", "retrieval", "ranking", "search", "embedding", "llm", "rag")))
    if cv >= 3 and ir == 0 and not any(kw in text for kw in CAREER_IR_KEYWORDS):
        return 0.40
    return 1.0


def _langchain_trap_penalty(candidate: dict[str, Any], skills: set[str]) -> float:
    text = _candidate_text(candidate)
    if ("langchain" in text or any("langchain" in s for s in skills)) and not any(
        k in text for k in ("pytorch", "tensorflow", "fine-tun", "embedding", "faiss", "ndcg", "retrieval")
    ):
        return 0.55
    return 1.0


def _honeypot_penalty(candidate: dict[str, Any]) -> float:
    profile = candidate.get("profile", {})
    years = profile.get("years_of_experience", 0)
    history = candidate.get("career_history", [])
    months = sum(j.get("duration_months", 0) for j in history)
    if years > 0 and months > 0:
        exp = years * 12
        if months > exp * 2.5 or months < exp * 0.25:
            return 0.03
    if candidate.get("redrob_signals", {}).get("notice_period_days", 0) > 180:
        return 0.03
    return 1.0


def _core_skill_score(skills: set[str], text: str) -> float:
    matched = {c for c in CORE_SKILLS if c in skills or c in text}
    return min(len(matched) / 7, 1.0)


def _deep_score(
    candidate: dict[str, Any],
    text: str,
    semantic: float,
) -> tuple[float, dict[str, float]]:
    profile = candidate.get("profile", {})
    skills = _skill_names(candidate)
    signals = candidate.get("redrob_signals", {})

    skill_raw = _core_skill_score(skills, text) * _skill_trust_multiplier(candidate)
    skill_component = skill_raw * 0.65 + _assessment_boost(signals) * 0.35
    title_component = _title_score(profile.get("current_title", ""), profile.get("headline", ""))
    career_component = _career_relevance_score(candidate)
    exp_component = _experience_score(profile.get("years_of_experience", 0))
    loc_component = _location_score(profile.get("location", ""), profile.get("country", ""))
    tenure_component = _tenure_stability(candidate)
    edu_component = _education_boost(candidate)

    base = (
        title_component * 0.30
        + career_component * 0.24
        + skill_component * 0.18
        + exp_component * 0.10
        + loc_component * 0.08
        + semantic * 0.06
        + tenure_component * 0.02
        + edu_component * 0.02
    )

    behavioral = _behavioral_multiplier(signals)
    penalties = (
        _consulting_penalty(candidate)
        * _cv_only_penalty(skills, text)
        * _langchain_trap_penalty(candidate, skills)
        * _honeypot_penalty(candidate)
    )
    final = base * behavioral * penalties

    breakdown = {
        "skills": round(skill_component, 3),
        "title": round(title_component, 3),
        "career": round(career_component, 3),
        "experience": round(exp_component, 3),
        "location": round(loc_component, 3),
        "semantic": round(semantic, 3),
        "tenure": round(tenure_component, 3),
        "education": round(edu_component, 3),
        "behavioral": round(behavioral, 3),
        "penalties": round(penalties, 3),
        "final": round(final, 3),
    }
    return final, breakdown


def _generate_reasoning(candidate: dict[str, Any], breakdown: dict[str, float], audit: dict[str, Any]) -> str:
    profile = candidate.get("profile", {})
    signals = candidate.get("redrob_signals", {})
    skills = _skill_names(candidate)
    core = [s for s in sorted(skills) if any(c in s for c in ("python", "embed", "retriev", "rank", "llm", "vector", "faiss", "nlp", "rag"))]

    parts = [
        f"{profile.get('current_title', 'Professional')} at {profile.get('current_company', 'N/A')} "
        f"with {profile.get('years_of_experience', 0):.1f} yrs",
    ]
    if breakdown.get("career", 0) >= 0.45:
        parts.append("shipped ranking/retrieval/production systems in career history")
    if core:
        parts.append(f"{len(core)} core AI/IR skills including {', '.join(core[:3])}")
    parts.append(f"based in {profile.get('location', 'unknown')}")
    rr = signals.get("recruiter_response_rate")
    if isinstance(rr, (int, float)):
        parts.append(f"response rate {rr:.2f}")
    notice = signals.get("notice_period_days")
    if isinstance(notice, int) and notice > 60:
        parts.append(f"notice {notice}d is a concern")
    if audit.get("fit_tier") == "Strong Fit":
        parts.append("high cross-check confidence")
    return "; ".join(parts) + "."


def rank_candidates(
    candidates: list[dict[str, Any]],
    job_description: str,
    top_n: int = 100,
) -> list[RankedCandidate]:
    if not candidates:
        return []

    texts = [_candidate_text(c) for c in candidates]
    vectorizer = TfidfVectorizer(max_features=12000, ngram_range=(1, 2), stop_words="english", sublinear_tf=True)
    tfidf = vectorizer.fit_transform(texts + [job_description.lower()])
    semantics = cosine_similarity(tfidf[:-1], tfidf[-1]).flatten()

    # ── Stage 1: recall shortlist for large pools ──────────────────────────
    if len(candidates) > 500:
        recall_scored = [
            (i, _fast_recall_score(candidates[i], float(semantics[i])))
            for i in range(len(candidates))
        ]
        recall_scored.sort(key=lambda x: -x[1])
        shortlist_idx = [i for i, s in recall_scored[:RECALL_TOP_K] if s > 0]
    else:
        shortlist_idx = list(range(len(candidates)))

    # ── Stage 2: deep precision scoring ──────────────────────────────────
    scored: list[tuple[str, float, dict, dict, dict]] = []
    for idx in shortlist_idx:
        c = candidates[idx]
        final, breakdown = _deep_score(c, texts[idx], float(semantics[idx]))
        audit = cross_check_candidate(c, breakdown)
        if audit.get("fit_tier") == "Concern" and breakdown.get("penalties", 1) < 0.15:
            continue
        scored.append((c["candidate_id"], final, c, breakdown, audit))

    scored.sort(key=lambda x: (-x[1], x[0]))

    # ── Stage 3: iterative re-rank — demote flagged traps in top band ─────
    clean: list[tuple] = []
    demoted: list[tuple] = []
    for item in scored:
        if item[4].get("audit_flags") and "KEYWORD_STUFFER_TRAP" in item[4]["audit_flags"]:
            demoted.append(item)
        else:
            clean.append(item)
    final_order = clean + demoted
    top = final_order[:top_n]

    results: list[RankedCandidate] = []
    for rank_idx, (cid, raw, candidate, breakdown, audit) in enumerate(top, start=1):
        normalized = max(0.01, round(1.0 - (rank_idx - 1) * 0.008, 4))
        profile = candidate.get("profile", {})
        results.append(RankedCandidate(
            candidate_id=cid,
            rank=rank_idx,
            score=normalized,
            reasoning=_generate_reasoning(candidate, breakdown, audit),
            profile_summary={
                "name": profile.get("anonymized_name"),
                "title": profile.get("current_title"),
                "company": profile.get("current_company"),
                "location": profile.get("location"),
                "years_of_experience": profile.get("years_of_experience"),
                "headline": profile.get("headline"),
                "skills": [s.get("name") for s in candidate.get("skills", [])[:8]],
                "open_to_work": candidate.get("redrob_signals", {}).get("open_to_work_flag"),
                "response_rate": candidate.get("redrob_signals", {}).get("recruiter_response_rate"),
                "notice_period_days": candidate.get("redrob_signals", {}).get("notice_period_days"),
            },
            score_breakdown=breakdown,
            audit=audit,
        ))

    return results


def write_submission(results: list[RankedCandidate], output_path: Path) -> None:
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])
        for r in results:
            writer.writerow([r.candidate_id, r.rank, r.score, r.reasoning])


def run_ranking(
    candidates_path: Path,
    job_description_path: Path,
    output_path: Path | None = None,
    top_n: int = 100,
) -> list[RankedCandidate]:
    candidates = load_candidates(candidates_path)
    job_description = job_description_path.read_text(encoding="utf-8")
    results = rank_candidates(candidates, job_description, top_n=top_n)
    if output_path:
        write_submission(results, output_path)
    return results
