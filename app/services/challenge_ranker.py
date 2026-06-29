"""
CPU-only candidate ranker for the Redrob hackathon challenge.

Designed per submission_spec + redrob_signals_doc:
- Title/career history are decisive (not keyword stuffing)
- Behavioral signals modify skill-match scores
- Honeypot and trap profiles are penalized
- No network calls during ranking
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
}

CONSULTING_FIRMS = {
    "tcs", "infosys", "wipro", "accenture", "cognizant", "capgemini", "mindtree",
    "hcl", "tech mahindra", "ltimindtree", "mphasis", "persistent", "lti",
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
    "a/b test", "ndcg", "recsys", "re-rank",
}

PRODUCT_INDICATORS = {
    "product", "startup", "series", "saas", "platform", "scale", "users",
    "production", "deployed", "shipped", "a/b",
}


@dataclass
class RankedCandidate:
    candidate_id: str
    rank: int
    score: float
    reasoning: str
    profile_summary: dict[str, Any]
    score_breakdown: dict[str, float] = field(default_factory=dict)


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
        profile.get("headline", ""),
        profile.get("summary", ""),
        profile.get("current_title", ""),
        profile.get("current_company", ""),
        profile.get("current_industry", ""),
        profile.get("location", ""),
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


def _skill_trust_multiplier(candidate: dict[str, Any]) -> float:
    skills = candidate.get("skills", [])
    if not skills:
        return 0.5
    trusted = 0.0
    for skill in skills:
        endorsements = skill.get("endorsements", 0)
        duration = skill.get("duration_months", 0)
        proficiency = skill.get("proficiency", "beginner")
        if endorsements > 30 and duration < 6:
            continue
        if proficiency in ("advanced", "expert") and duration >= 12:
            trusted += 1.5
        elif proficiency in ("intermediate", "advanced"):
            trusted += 1.0
        else:
            trusted += 0.5
    return min(trusted / max(len(skills), 1), 1.0)


def _assessment_boost(signals: dict[str, Any], skills: set[str]) -> float:
    assessments = signals.get("skill_assessment_scores") or {}
    if not assessments:
        return 0.5
    relevant = []
    for skill_name, score in assessments.items():
        sl = skill_name.lower()
        if any(c in sl for c in ("python", "ml", "nlp", "retriev", "rank", "embed", "search")):
            relevant.append(score / 100.0)
    return sum(relevant) / len(relevant) if relevant else 0.5


def _behavioral_multiplier(signals: dict[str, Any]) -> float:
    if not signals:
        return 0.7
    multiplier = 1.0
    if signals.get("open_to_work_flag"):
        multiplier *= 1.05
    response_rate = signals.get("recruiter_response_rate", 0)
    if response_rate >= 0.5:
        multiplier *= 1.08
    elif response_rate < 0.15:
        multiplier *= 0.82
    notice = signals.get("notice_period_days", 90)
    if notice <= 30:
        multiplier *= 1.06
    elif notice > 90:
        multiplier *= 0.9
    saved = signals.get("saved_by_recruiters_30d", 0)
    if saved >= 3:
        multiplier *= 1.05
    interview_rate = signals.get("interview_completion_rate", 0)
    if interview_rate >= 0.8:
        multiplier *= 1.03
    elif interview_rate < 0.3:
        multiplier *= 0.88
    views = signals.get("profile_views_received_30d", 0)
    if views >= 10:
        multiplier *= 1.03
    completeness = signals.get("profile_completeness_score", 50) / 100.0
    multiplier *= 0.9 + 0.1 * completeness
    last_active = _parse_date(signals.get("last_active_date"))
    if last_active:
        days_inactive = (date.today() - last_active).days
        if days_inactive > 180:
            multiplier *= 0.75
        elif days_inactive > 90:
            multiplier *= 0.88
    github = signals.get("github_activity_score", -1)
    if github >= 50:
        multiplier *= 1.04
    return min(max(multiplier, 0.55), 1.25)


def _title_score(title: str, headline: str) -> float:
    combined = f"{title} {headline}".lower()
    for weak in WEAK_TITLES:
        if weak in combined:
            return 0.15
    for strong in STRONG_TITLES:
        if strong in combined:
            return 1.0
    if any(kw in combined for kw in ("engineer", "scientist", "architect")):
        return 0.75
    return 0.45


def _career_relevance_score(candidate: dict[str, Any]) -> float:
    """Score career history for IR/ranking/production signals (JD hackathon note)."""
    hits = 0
    product_hits = 0
    for job in candidate.get("career_history", []):
        desc = (job.get("description") or "").lower()
        title = (job.get("title") or "").lower()
        combined = f"{title} {desc}"
        if any(kw in combined for kw in CAREER_IR_KEYWORDS):
            hits += 1
        if any(kw in combined for kw in PRODUCT_INDICATORS):
            product_hits += 1
    history_len = max(len(candidate.get("career_history", [])), 1)
    return min((hits / history_len) * 0.6 + (product_hits / history_len) * 0.4, 1.0)


def _experience_score(years: float) -> float:
    if 5 <= years <= 9:
        return 1.0
    if 4 <= years <= 12:
        return 0.85
    if 3 <= years <= 15:
        return 0.65
    return 0.35


def _location_score(location: str, country: str) -> float:
    loc = f"{location} {country}".lower()
    if any(city in loc for city in INDIA_LOCATIONS):
        return 1.0
    if country.lower() == "india":
        return 0.9
    return 0.45


def _consulting_penalty(candidate: dict[str, Any]) -> float:
    companies = [candidate.get("profile", {}).get("current_company", "").lower()]
    companies.extend(j.get("company", "").lower() for j in candidate.get("career_history", []))
    consulting_count = sum(1 for c in companies if any(firm in c for firm in CONSULTING_FIRMS))
    total = max(len(companies), 1)
    if consulting_count == total:
        return 0.5
    if consulting_count > total * 0.6:
        return 0.72
    return 1.0


def _cv_only_penalty(skills: set[str], text: str) -> float:
    cv_hits = sum(1 for s in skills if any(cv in s for cv in CV_ONLY_SKILLS))
    ir_hits = sum(
        1 for s in skills
        if any(k in s for k in ("nlp", "retrieval", "ranking", "search", "embedding", "llm", "rag"))
    )
    ir_in_career = any(kw in text for kw in CAREER_IR_KEYWORDS)
    if cv_hits >= 3 and ir_hits == 0 and not ir_in_career:
        return 0.45
    return 1.0


def _langchain_trap_penalty(candidate: dict[str, Any], skills: set[str]) -> float:
    """Penalize shallow LangChain-only AI profiles."""
    text = _candidate_text(candidate)
    has_langchain = "langchain" in text or any("langchain" in s for s in skills)
    has_deep_ml = any(
        k in text for k in ("pytorch", "tensorflow", "fine-tun", "embedding", "faiss", "ndcg", "retrieval")
    )
    if has_langchain and not has_deep_ml:
        return 0.6
    return 1.0


def _honeypot_penalty(candidate: dict[str, Any]) -> float:
    profile = candidate.get("profile", {})
    years = profile.get("years_of_experience", 0)
    history = candidate.get("career_history", [])
    total_months = sum(j.get("duration_months", 0) for j in history)
    if years > 0 and total_months > 0:
        expected_months = years * 12
        if total_months > expected_months * 2.5 or total_months < expected_months * 0.3:
            return 0.05
    signals = candidate.get("redrob_signals", {})
    if signals.get("notice_period_days", 0) > 180:
        return 0.05
    return 1.0


def _core_skill_score(skills: set[str], text: str) -> float:
    matched = {core for core in CORE_SKILLS if core in skills or core in text}
    return min(len(matched) / 8, 1.0)


def _generate_reasoning(candidate: dict[str, Any], breakdown: dict[str, float]) -> str:
    profile = candidate.get("profile", {})
    signals = candidate.get("redrob_signals", {})
    skills = _skill_names(candidate)
    core_matched = [
        s for s in sorted(skills)
        if any(c in s for c in ("python", "embed", "retriev", "rank", "llm", "vector", "faiss", "nlp", "rag"))
    ]
    title = profile.get("current_title", "Professional")
    years = profile.get("years_of_experience", 0)
    location = profile.get("location", "unknown")
    company = profile.get("current_company", "")
    notice = signals.get("notice_period_days")
    response = signals.get("recruiter_response_rate")

    parts = [f"{title} at {company} with {years:.1f} yrs"]
    if breakdown.get("career", 0) >= 0.5:
        parts.append("career history shows ranking/retrieval/production work")
    if core_matched:
        parts.append(f"skills include {', '.join(core_matched[:3])}")
    parts.append(f"based in {location}")
    if isinstance(response, (int, float)):
        parts.append(f"response rate {response:.2f}")
    if isinstance(notice, int) and notice > 60:
        parts.append(f"notice period {notice} days is a concern")
    if breakdown.get("title", 1) < 0.3:
        parts.append("title mismatch for Senior AI Engineer role")
    if breakdown.get("behavioral", 1) < 0.85:
        parts.append("low engagement signals")
    return "; ".join(parts) + "."


def rank_candidates(
    candidates: list[dict[str, Any]],
    job_description: str,
    top_n: int = 100,
) -> list[RankedCandidate]:
    if not candidates:
        return []

    texts = [_candidate_text(c) for c in candidates]
    vectorizer = TfidfVectorizer(max_features=10000, ngram_range=(1, 2), stop_words="english")
    tfidf_matrix = vectorizer.fit_transform(texts + [job_description.lower()])
    semantic_scores = cosine_similarity(tfidf_matrix[:-1], tfidf_matrix[-1]).flatten()

    scored: list[tuple[str, float, dict[str, Any], dict[str, float]]] = []

    for idx, candidate in enumerate(candidates):
        profile = candidate.get("profile", {})
        skills = _skill_names(candidate)
        text = texts[idx]
        signals = candidate.get("redrob_signals", {})

        skill_raw = _core_skill_score(skills, text) * _skill_trust_multiplier(candidate)
        assessment = _assessment_boost(signals, skills)
        skill_component = skill_raw * 0.7 + assessment * 0.3

        title_component = _title_score(profile.get("current_title", ""), profile.get("headline", ""))
        career_component = _career_relevance_score(candidate)
        exp_component = _experience_score(profile.get("years_of_experience", 0))
        loc_component = _location_score(profile.get("location", ""), profile.get("country", ""))
        semantic_component = float(semantic_scores[idx])

        base = (
            skill_component * 0.22
            + title_component * 0.28
            + career_component * 0.20
            + exp_component * 0.12
            + loc_component * 0.08
            + semantic_component * 0.10
        )

        behavioral = _behavioral_multiplier(signals)
        penalties = (
            _consulting_penalty(candidate)
            * _cv_only_penalty(skills, text)
            * _langchain_trap_penalty(candidate, skills)
            * _honeypot_penalty(candidate)
        )
        final_score = base * behavioral * penalties

        breakdown = {
            "skills": round(skill_component, 3),
            "title": round(title_component, 3),
            "career": round(career_component, 3),
            "experience": round(exp_component, 3),
            "location": round(loc_component, 3),
            "semantic": round(semantic_component, 3),
            "behavioral": round(behavioral, 3),
            "penalties": round(penalties, 3),
            "final": round(final_score, 3),
        }
        scored.append((candidate["candidate_id"], final_score, candidate, breakdown))

    scored.sort(key=lambda x: (-x[1], x[0]))
    top = scored[:top_n]

    results: list[RankedCandidate] = []
    for rank_idx, (cid, raw_score, candidate, breakdown) in enumerate(top, start=1):
        normalized = max(0.01, round(1.0 - (rank_idx - 1) * 0.008, 4))
        profile = candidate.get("profile", {})
        results.append(RankedCandidate(
            candidate_id=cid,
            rank=rank_idx,
            score=normalized,
            reasoning=_generate_reasoning(candidate, breakdown),
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
