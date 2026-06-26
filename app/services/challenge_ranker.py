"""
CPU-only candidate ranker for the Redrob hackathon challenge.
No network calls during ranking — uses TF-IDF + rule-based scoring.
"""

from __future__ import annotations

import csv
import gzip
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Key skills from the JD (must-have and nice-to-have)
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


@dataclass
class RankedCandidate:
    candidate_id: str
    rank: int
    score: float
    reasoning: str
    profile_summary: dict[str, Any]


def load_candidates(path: Path) -> list[dict[str, Any]]:
    """Load candidates from .json, .jsonl, or .jsonl.gz."""
    suffixes = "".join(path.suffixes).lower()
    if suffixes == ".json":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else [data]
    if suffixes.endswith(".gz"):
        opener = gzip.open(path, "rt", encoding="utf-8")
    else:
        opener = open(path, encoding="utf-8")
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


def _skill_trust_multiplier(candidate: dict[str, Any]) -> float:
    """Penalize keyword stuffers with high endorsements but low duration."""
    skills = candidate.get("skills", [])
    if not skills:
        return 0.5
    trusted = 0
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
        multiplier *= 0.85
    notice = signals.get("notice_period_days", 90)
    if notice <= 30:
        multiplier *= 1.06
    elif notice > 90:
        multiplier *= 0.92
    saved = signals.get("saved_by_recruiters_30d", 0)
    if saved >= 3:
        multiplier *= 1.04
    interview_rate = signals.get("interview_completion_rate", 0)
    if interview_rate >= 0.8:
        multiplier *= 1.03
    elif interview_rate < 0.3:
        multiplier *= 0.9
    return min(max(multiplier, 0.6), 1.2)


def _title_score(title: str, headline: str) -> float:
    combined = f"{title} {headline}".lower()
    for strong in STRONG_TITLES:
        if strong in combined:
            return 1.0
    if any(kw in combined for kw in ("engineer", "scientist", "architect")):
        return 0.7
    if any(kw in combined for kw in ("manager", "analyst", "writer", "designer")):
        return 0.3
    return 0.5


def _experience_score(years: float) -> float:
    if 5 <= years <= 9:
        return 1.0
    if 4 <= years <= 12:
        return 0.85
    if 3 <= years <= 15:
        return 0.65
    return 0.4


def _location_score(location: str, country: str) -> float:
    loc = f"{location} {country}".lower()
    if any(city in loc for city in INDIA_LOCATIONS):
        return 1.0
    if country.lower() in ("india",):
        return 0.9
    return 0.5


def _consulting_penalty(candidate: dict[str, Any]) -> float:
    companies = []
    profile = candidate.get("profile", {})
    companies.append(profile.get("current_company", "").lower())
    for job in candidate.get("career_history", []):
        companies.append(job.get("company", "").lower())
    consulting_count = sum(
        1 for c in companies
        if any(firm in c for firm in CONSULTING_FIRMS)
    )
    total = max(len(companies), 1)
    if consulting_count == total:
        return 0.55
    if consulting_count > total * 0.6:
        return 0.75
    return 1.0


def _cv_only_penalty(skills: set[str]) -> float:
    cv_hits = sum(1 for s in skills if any(cv in s for cv in CV_ONLY_SKILLS))
    ir_hits = sum(
        1 for s in skills
        if any(k in s for k in ("nlp", "retrieval", "ranking", "search", "embedding", "llm", "rag"))
    )
    if cv_hits >= 3 and ir_hits == 0:
        return 0.5
    return 1.0


def _honeypot_penalty(candidate: dict[str, Any]) -> float:
    """Detect subtly impossible profiles."""
    profile = candidate.get("profile", {})
    years = profile.get("years_of_experience", 0)
    history = candidate.get("career_history", [])
    total_months = sum(j.get("duration_months", 0) for j in history)
    if years > 0 and total_months > 0:
        expected_months = years * 12
        if total_months > expected_months * 2.5 or total_months < expected_months * 0.3:
            return 0.1
    signals = candidate.get("redrob_signals", {})
    notice = signals.get("notice_period_days", 0)
    if notice > 180:
        return 0.1
    return 1.0


def _core_skill_score(skills: set[str], text: str) -> float:
    matched = set()
    for core in CORE_SKILLS:
        if core in skills or core in text:
            matched.add(core)
    return min(len(matched) / 8, 1.0)


def _generate_reasoning(candidate: dict[str, Any], score: float) -> str:
    profile = candidate.get("profile", {})
    signals = candidate.get("redrob_signals", {})
    skills = _skill_names(candidate)
    core_matched = [s for s in sorted(skills) if any(c in s for c in ("python", "embed", "retriev", "rank", "llm", "vector", "faiss", "nlp", "rag"))]
    title = profile.get("current_title", "Professional")
    years = profile.get("years_of_experience", 0)
    location = profile.get("location", "unknown")
    notice = signals.get("notice_period_days", "unknown")
    response = signals.get("recruiter_response_rate")
    parts = [f"{title} with {years:.1f} yrs"]
    if core_matched:
        parts.append(f"strong in {', '.join(core_matched[:3])}")
    parts.append(f"based in {location}")
    if isinstance(response, (int, float)):
        parts.append(f"response rate {response:.2f}")
    if isinstance(notice, int) and notice > 60:
        parts.append(f"notice period {notice} days is a concern")
    elif score < 0.5:
        parts.append("adjacent skills only")
    return "; ".join(parts) + "."


def rank_candidates(
    candidates: list[dict[str, Any]],
    job_description: str,
    top_n: int = 100,
) -> list[RankedCandidate]:
    if not candidates:
        return []

    texts = [_candidate_text(c) for c in candidates]
    vectorizer = TfidfVectorizer(max_features=8000, ngram_range=(1, 2), stop_words="english")
    tfidf_matrix = vectorizer.fit_transform(texts + [job_description.lower()])
    jd_vector = tfidf_matrix[-1]
    candidate_vectors = tfidf_matrix[:-1]
    semantic_scores = cosine_similarity(candidate_vectors, jd_vector).flatten()

    scored: list[tuple[str, float, dict[str, Any]]] = []

    for idx, candidate in enumerate(candidates):
        profile = candidate.get("profile", {})
        skills = _skill_names(candidate)
        text = texts[idx]
        signals = candidate.get("redrob_signals", {})

        skill_component = _core_skill_score(skills, text) * _skill_trust_multiplier(candidate)
        title_component = _title_score(profile.get("current_title", ""), profile.get("headline", ""))
        exp_component = _experience_score(profile.get("years_of_experience", 0))
        loc_component = _location_score(profile.get("location", ""), profile.get("country", ""))
        semantic_component = float(semantic_scores[idx])

        base = (
            skill_component * 0.30
            + title_component * 0.25
            + exp_component * 0.15
            + loc_component * 0.10
            + semantic_component * 0.20
        )

        multiplier = (
            _behavioral_multiplier(signals)
            * _consulting_penalty(candidate)
            * _cv_only_penalty(skills)
            * _honeypot_penalty(candidate)
        )
        final_score = base * multiplier
        scored.append((candidate["candidate_id"], final_score, candidate))

    scored.sort(key=lambda x: (-x[1], x[0]))
    top = scored[:top_n]

    results: list[RankedCandidate] = []
    for rank_idx, (cid, raw_score, candidate) in enumerate(top, start=1):
        normalized = max(0.01, 1.0 - (rank_idx - 1) * 0.008)
        profile = candidate.get("profile", {})
        results.append(RankedCandidate(
            candidate_id=cid,
            rank=rank_idx,
            score=round(normalized, 4),
            reasoning=_generate_reasoning(candidate, raw_score),
            profile_summary={
                "name": profile.get("anonymized_name"),
                "title": profile.get("current_title"),
                "location": profile.get("location"),
                "years_of_experience": profile.get("years_of_experience"),
                "skills": [s.get("name") for s in candidate.get("skills", [])[:8]],
            },
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
