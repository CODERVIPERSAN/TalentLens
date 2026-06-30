"""
TalentLens v4 Ranker — hybrid BM25 + TF-IDF + LTR + fraud detection.

PUB constraints: CPU only, ≤5 min, ≤16GB RAM, NO network during ranking.
Pre-compute offline: python scripts/precompute_ranker_assets.py
"""

from __future__ import annotations

import csv
import gc
import gzip
import heapq
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterator

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.services.bm25_recall import BM25Index, StreamingBM25, tokenize
from app.services.fraud_detector import fraud_penalty, fraud_risk_score, is_honeypot
from app.services.ltr_ranker import (
    embedding_similarity,
    extract_features,
    load_embedding_index,
    load_ltr_model,
    predict_ltr,
)
from app.services.memory_config import low_memory_mode, recall_top_k, release_memory, tfidf_max_features, use_embedding_cache
from app.services.rank_auditor import cross_check_candidate
from app.services.rank_features import (
    has_career_ir_proof,
    is_ghost_unavailable,
    is_research_only,
)

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

RECALL_TOP_K = 5000  # overridden by memory_config.recall_top_k() for large pools
RULE_WEIGHT = 0.52
LTR_WEIGHT = 0.48
STREAMING_JSONL_MIN_BYTES = 5_000_000


@dataclass
class RankedCandidate:
    candidate_id: str
    rank: int
    score: float
    reasoning: str
    profile_summary: dict[str, Any]
    score_breakdown: dict[str, float] = field(default_factory=dict)
    audit: dict[str, Any] = field(default_factory=dict)


def iter_candidates(path: Path) -> Iterator[dict[str, Any]]:
    """Stream candidates one at a time (memory-safe for 100K jsonl)."""
    suffixes = "".join(path.suffixes).lower()
    if suffixes == ".json":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        items = data if isinstance(data, list) else [data]
        yield from items
        return
    opener = gzip.open(path, "rt", encoding="utf-8") if suffixes.endswith(".gz") else open(path, encoding="utf-8")
    with opener as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def load_candidates(path: Path) -> list[dict[str, Any]]:
    """Load all candidates — use only for small pools (sample JSON)."""
    return list(iter_candidates(path))


def find_candidate_by_id(path: Path, candidate_id: str) -> dict[str, Any] | None:
    for candidate in iter_candidates(path):
        if candidate.get("candidate_id") == candidate_id:
            return candidate
    return None


def _light_recall_text(candidate: dict[str, Any]) -> str:
    """Compact profile text for recall/BM25 — caps long fields to save RAM."""
    profile = candidate.get("profile", {})
    parts = [
        profile.get("headline", ""), profile.get("current_title", ""),
        profile.get("current_company", ""), profile.get("location", ""),
        profile.get("summary", "")[:300],
    ]
    parts.extend(s.get("name", "") for s in candidate.get("skills", [])[:14])
    for job in candidate.get("career_history", [])[:4]:
        parts.extend([job.get("title", ""), job.get("company", "")])
        desc = job.get("description", "") or ""
        parts.append(desc[:220])
    return " ".join(p for p in parts if p).lower()


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


def _fast_recall_score(candidate: dict[str, Any], semantic: float, bm25_norm: float = 0.0) -> float:
    """Stage-1 lightweight score for 100K recall."""
    if is_honeypot(candidate):
        return 0.0
    profile = candidate.get("profile", {})
    title = _title_score(profile.get("current_title", ""), profile.get("headline", ""))
    if title <= 0.15:
        return 0.0
    return (
        title * 0.38
        + semantic * 0.22
        + bm25_norm * 0.20
        + _career_relevance_score(candidate) * 0.20
    )


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


def _ghost_penalty(signals: dict[str, Any]) -> float:
    if is_ghost_unavailable(signals):
        return 0.08
    return 1.0


def _research_only_penalty(text: str) -> float:
    if is_research_only(text):
        return 0.50
    return 1.0


def _career_boost_without_keywords(candidate: dict[str, Any], skill_component: float) -> float:
    """JD Tier-5: career proof matters more than skill buzzwords."""
    if skill_component < 0.35 and has_career_ir_proof(candidate):
        return 1.18
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
        * _research_only_penalty(text)
        * fraud_penalty(candidate)
    )
    career_boost = _career_boost_without_keywords(candidate, skill_component)
    final = base * behavioral * penalties * career_boost

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
        "career_boost": round(career_boost, 3),
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


def _semantic_scores(texts: list[str], job_description: str) -> list[float]:
    vectorizer = TfidfVectorizer(
        max_features=tfidf_max_features(),
        ngram_range=(1, 2),
        stop_words="english",
        sublinear_tf=True,
    )
    tfidf = vectorizer.fit_transform(texts + [job_description.lower()])
    return cosine_similarity(tfidf[:-1], tfidf[-1]).flatten().tolist()
    # vectorizer + matrix freed when function returns


def _jd_overlap_recall(text: str) -> float:
    """Fast lexical recall without full TF-IDF — used on 100K pool."""
    hits = sum(1 for term in CORE_SKILLS if term in text)
    return min(hits / 8.0, 1.0)


def _stream_recall_shortlist(path: Path, job_description: str) -> tuple[list[dict[str, Any]], int]:
    """
    Two-pass streaming recall — never holds 100K full profiles in RAM.
    Pass 1: BM25 corpus stats. Pass 2: recall heap + load shortlist only.
    """
    k = recall_top_k()

    def _token_stream() -> Iterator[list[str]]:
        for candidate in iter_candidates(path):
            yield tokenize(_light_recall_text(candidate))

    bm25 = StreamingBM25.from_token_streams(_token_stream())
    release_memory()

    heap: list[tuple[float, str]] = []
    bm25_heap: list[tuple[float, str]] = []
    bm25_target = k // 2

    pool_size = 0
    for candidate in iter_candidates(path):
        pool_size += 1
        cid = candidate["candidate_id"]
        light = _light_recall_text(candidate)
        tokens = tokenize(light)
        bscore = bm25.score(tokens)

        if len(bm25_heap) < bm25_target:
            heapq.heappush(bm25_heap, (bscore, cid))
        elif bscore > bm25_heap[0][0]:
            heapq.heapreplace(bm25_heap, (bscore, cid))

        lex = _jd_overlap_recall(light)
        bm25_norm = min(bscore / 40.0, 1.0)
        score = _fast_recall_score(candidate, lex, bm25_norm)
        if score <= 0:
            continue
        entry = (-score, cid)
        if len(heap) < k:
            heapq.heappush(heap, entry)
        elif score > -heap[0][0]:
            heapq.heapreplace(heap, entry)

    recall_ids = {cid for _, cid in heap}
    recall_ids.update(cid for _, cid in bm25_heap)
    target = len(recall_ids)
    del heap, bm25_heap, bm25
    release_memory()

    shortlist: list[dict[str, Any]] = []
    for candidate in iter_candidates(path):
        cid = candidate["candidate_id"]
        if cid in recall_ids:
            shortlist.append(candidate)
            if len(shortlist) >= target:
                break
    recall_ids.clear()
    release_memory()
    return shortlist, pool_size


def rank_candidates_from_path(path: Path, job_description: str, top_n: int = 100) -> list[RankedCandidate]:
    """Memory-safe entry point for large jsonl pools."""
    shortlist, pool_size = _stream_recall_shortlist(path, job_description)
    results = rank_candidates(shortlist, job_description, top_n=top_n)
    release_memory()
    return results


def rank_candidates(
    candidates: list[dict[str, Any]],
    job_description: str,
    top_n: int = 100,
) -> list[RankedCandidate]:
    if not candidates:
        return []

    texts = [_candidate_text(c) for c in candidates]
    ltr_model = load_ltr_model()
    emb_index = load_embedding_index() if use_embedding_cache() else None
    jd_emb = None
    if emb_index is not None:
        try:
            import numpy as np
            p = Path("data/ranker_cache/jd_embedding.npy")
            if p.exists():
                jd_emb = np.load(p, mmap_mode="r")
        except Exception:
            jd_emb = None

    recall_k = recall_top_k()

    # ── Stage 1: BM25 + lexical fusion recall (in-memory shortlist only) ─
    if len(candidates) > 500:
        light_texts = [_light_recall_text(c) for c in candidates]
        bm25 = BM25Index(light_texts)
        bm25_hits = {i: s for i, s in bm25.top_k(job_description, recall_k * 2)}
        bm25_max = max(bm25_hits.values()) if bm25_hits else 1.0
        del light_texts, bm25
        release_memory()

        recall_scored: list[tuple[int, float]] = []
        for i, c in enumerate(candidates):
            lex = _jd_overlap_recall(texts[i])
            bm25_norm = bm25_hits.get(i, 0.0) / bm25_max
            score = _fast_recall_score(c, lex, bm25_norm)
            if score > 0:
                recall_scored.append((i, score))
        recall_scored.sort(key=lambda x: -x[1])
        shortlist_idx = list(dict.fromkeys(
            [i for i, _ in recall_scored[:recall_k]]
            + [i for i in bm25_hits if bm25_hits[i] > bm25_max * 0.3][:recall_k // 2]
        ))[:recall_k]
        del recall_scored, bm25_hits
        release_memory()

        bm25_map = {i: 0.0 for i in shortlist_idx}
        shortlist_texts = [texts[i] for i in shortlist_idx]
        semantics_short = _semantic_scores(shortlist_texts, job_description)
        semantic_map = {shortlist_idx[i]: semantics_short[i] for i in range(len(shortlist_idx))}
        del shortlist_texts, semantics_short
        release_memory()
    else:
        shortlist_idx = list(range(len(candidates)))
        bm25_map = {i: 0.0 for i in shortlist_idx}
        semantics_all = _semantic_scores(texts, job_description)
        semantic_map = {i: semantics_all[i] for i in range(len(candidates))}

    # ── Stage 2+3: deep rule score + LTR blend + fraud gate ──────────────
    scored: list[tuple[str, float, dict, dict, dict]] = []
    for idx in shortlist_idx:
        c = candidates[idx]
        sem = float(semantic_map.get(idx, 0.0))
        if emb_index is not None and jd_emb is not None:
            emb_sim = embedding_similarity(c["candidate_id"], jd_emb, emb_index)
            sem = sem * 0.4 + emb_sim * 0.6

        final, breakdown = _deep_score(c, texts[idx], sem)
        breakdown["bm25"] = round(min(bm25_map.get(idx, 0) / 40.0, 1.0), 3)

        signals = c.get("redrob_signals", {})
        skills = _skill_names(c)
        skill_trust = _skill_trust_multiplier(c)
        assessment = _assessment_boost(signals)
        product_co = sum(
            1 for j in c.get("career_history", [])
            if any(pc in j.get("company", "").lower() for pc in PRODUCT_COMPANIES)
        ) / max(len(c.get("career_history", [])), 1)
        ir_jobs = sum(
            1 for j in c.get("career_history", [])
            if any(kw in f"{j.get('title','')} {j.get('description','')}".lower() for kw in CAREER_IR_KEYWORDS)
        ) / max(len(c.get("career_history", [])), 1)

        feat = extract_features(
            breakdown, bm25_map.get(idx, 0.0), skill_trust, assessment,
            product_co, ir_jobs, signals, fraud_risk_score(c),
        )
        ltr_score = predict_ltr(ltr_model, feat)
        blended = RULE_WEIGHT * final + LTR_WEIGHT * ltr_score
        breakdown["ltr"] = round(ltr_score, 3)
        breakdown["blended"] = round(blended, 3)
        breakdown["final"] = round(blended, 3)

        if is_honeypot(c) or breakdown.get("penalties", 1) < 0.10:
            continue

        audit = cross_check_candidate(c, breakdown)
        if audit.get("fit_tier") == "Concern" and breakdown.get("penalties", 1) < 0.20:
            continue
        scored.append((c["candidate_id"], blended, c, breakdown, audit))

    scored.sort(key=lambda x: (-x[1], x[0]))

    # ── Stage 4: demote fraud/traps from top band ────────────────────────
    trap_flags = {
        "KEYWORD_STUFFER_TRAP", "HONEYPOT_SUSPECT", "GHOST_UNAVAILABLE",
        "RESEARCH_ONLY", "CV_ONLY_PROFILE", "ENDORSEMENT_FRAUD", "CONSULTING_ONLY",
    }
    clean: list[tuple] = []
    demoted: list[tuple] = []
    for item in scored:
        flags = set(item[4].get("audit_flags", []))
        if flags & trap_flags:
            demoted.append(item)
        else:
            clean.append(item)
    final_order = clean + demoted
    top = final_order[:top_n]

    results: list[RankedCandidate] = []
    for rank_idx, (cid, raw, candidate, breakdown, audit) in enumerate(top, start=1):
        audit = cross_check_candidate(candidate, breakdown, rank=rank_idx)
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

    release_memory()
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
    job_description = job_description_path.read_text(encoding="utf-8")
    suffixes = "".join(candidates_path.suffixes).lower()
    use_streaming = (
        suffixes in (".jsonl", ".jsonl.gz")
        and candidates_path.exists()
        and candidates_path.stat().st_size >= STREAMING_JSONL_MIN_BYTES
    )
    if use_streaming:
        results = rank_candidates_from_path(candidates_path, job_description, top_n=top_n)
    else:
        candidates = load_candidates(candidates_path)
        results = rank_candidates(candidates, job_description, top_n=top_n)
    if output_path:
        write_submission(results, output_path)
    return results
