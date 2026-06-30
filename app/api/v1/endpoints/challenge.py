import csv
import io
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.challenge_data import (
    SUBMISSION_CSV,
    get_candidates_path,
    get_data_sources,
    get_job,
    load_candidates_page,
)
from app.services.challenge_ranker import (
    find_candidate_by_id,
    get_last_ollama_stats,
    rank_candidates,
    rank_candidates_from_path,
    write_submission,
)
from app.services.memory_config import low_memory_mode
from app.services.ollama_reasoning import OllamaConfig, generate_ollama_reasoning, is_ollama_available
from app.services.rank_auditor import audit_ranking

router = APIRouter()

_ranking_cache: dict[str, Any] | None = None


class RankingRequest(BaseModel):
    use_sample: bool = False
    top_n: int = Field(default=100, ge=1, le=100)
    use_ollama: bool = True
    ollama_top_n: int = Field(default=10, ge=1, le=100)


class RankingResult(BaseModel):
    candidate_id: str
    rank: int
    score: float
    reasoning: str
    profile_summary: dict[str, Any]
    score_breakdown: dict[str, float] = {}
    audit: dict[str, Any] = {}
    reasoning_source: str = "rule_based"


class RankingResponse(BaseModel):
    job: dict[str, Any]
    pool: str
    pool_size: int
    ranked_count: int
    runtime_ms: int = 0
    quality_report: dict[str, Any]
    ollama_reasoning: dict[str, Any] | None = None
    submission_file: str | None = None
    memory_warning: str | None = None
    source_file: str | None = None
    matches: list[RankingResult]


def _serialize_match(r) -> dict[str, Any]:
    return {
        "candidate_id": r.candidate_id,
        "rank": r.rank,
        "score": r.score,
        "reasoning": r.reasoning,
        "profile_summary": r.profile_summary,
        "score_breakdown": r.score_breakdown,
        "audit": r.audit,
        "reasoning_source": getattr(r, "reasoning_source", "rule_based"),
    }


@router.get("/stats")
async def get_challenge_stats():
    job = get_job()
    meta = get_data_sources()
    return {
        "sample_candidates": meta["sample_count"],
        "full_pool_size": meta["full_count"] or 100000,
        "job_title": job["title"],
        "company": job["company"],
        "ranking_ready": meta["sample_available"] or meta["full_available"],
        "full_pool_available": meta["full_available"],
        "default_pool": meta["default_pool"],
        "active_ranker_file": meta["active_ranker_file"],
        "sources": meta["sources"],
        "ranker_version": "pro-v4-low-mem" if low_memory_mode() else "pro-v4-hybrid-ltr",
        "low_memory_mode": low_memory_mode(),
        "recommend_sample_pool": False,
        "streaming_ranker": True,
        "ollama_available": is_ollama_available(),
        "ollama_model": "llama3.2",
        "default_ollama_top_n": 10,
    }


@router.get("/job")
async def get_challenge_job():
    return get_job()


@router.get("/candidates")
async def list_challenge_candidates(skip: int = 0, limit: int = 50, use_sample: bool = False):
    try:
        path = get_candidates_path(use_sample=use_sample)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    page, total = load_candidates_page(path, skip, limit)
    return {
        "pool": "sample" if use_sample else "full",
        "total": total,
        "source_file": str(path),
        "candidates": [
            {
                "candidate_id": c["candidate_id"],
                "name": c.get("profile", {}).get("anonymized_name"),
                "title": c.get("profile", {}).get("current_title"),
                "company": c.get("profile", {}).get("current_company"),
                "location": c.get("profile", {}).get("location"),
                "years_of_experience": c.get("profile", {}).get("years_of_experience"),
                "headline": c.get("profile", {}).get("headline"),
                "skills": [s.get("name") for s in c.get("skills", [])[:8]],
                "open_to_work": c.get("redrob_signals", {}).get("open_to_work_flag"),
                "response_rate": c.get("redrob_signals", {}).get("recruiter_response_rate"),
            }
            for c in page
        ],
    }


@router.get("/candidates/{candidate_id}")
async def get_challenge_candidate(candidate_id: str, use_sample: bool = True):
    try:
        path = get_candidates_path(use_sample=use_sample)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    candidate = find_candidate_by_id(path, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return candidate


@router.post("/rank", response_model=RankingResponse)
async def run_challenge_ranking(request: RankingRequest = RankingRequest()):
    global _ranking_cache

    job = get_job()
    job_description = job.get("description", "")
    if not job_description:
        raise HTTPException(status_code=404, detail="Job description not found")

    try:
        path = get_candidates_path(use_sample=request.use_sample)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    top_n = min(request.top_n, 100)
    ollama_cfg = None
    if request.use_ollama:
        ollama_cfg = OllamaConfig(
            enabled=is_ollama_available(),
            model="llama3.2",
            top_n=min(request.ollama_top_n, top_n),
        )

    t0 = time.perf_counter()
    if request.use_sample:
        from app.services.challenge_ranker import load_candidates
        candidates = load_candidates(path)
        pool_size = len(candidates)
        results = rank_candidates(
            candidates,
            job_description,
            top_n=min(top_n, pool_size),
            ollama=ollama_cfg,
        )
    else:
        pool_size = get_data_sources().get("full_count") or 100000
        results = rank_candidates_from_path(
            path, job_description, top_n=top_n, ollama=ollama_cfg,
        )
    runtime_ms = round((time.perf_counter() - t0) * 1000)
    matches = [_serialize_match(r) for r in results]
    ollama_stats = get_last_ollama_stats() or {
        "enabled": bool(request.use_ollama),
        "available": is_ollama_available(),
        "model": "llama3.2",
        "top_n": request.ollama_top_n,
        "enriched": 0,
        "fallback": 0,
    }

    # Persist submission CSV on disk (same format as rank.py)
    write_submission(results, SUBMISSION_CSV)

    quality_report = audit_ranking(matches)

    payload = {
        "job": {
            "job_id": job.get("job_id"),
            "title": job["title"],
            "company": job["company"],
            "location": job["location"],
            "experience_range": job.get("experience_range"),
        },
        "pool": "sample" if request.use_sample else "full",
        "pool_size": pool_size,
        "source_file": str(path),
        "ranked_count": len(matches),
        "runtime_ms": runtime_ms,
        "submission_file": str(SUBMISSION_CSV.resolve()),
        "memory_warning": (
            "Low RAM — close extra browser tabs before ranking. Uses streaming (~300MB peak)."
            if low_memory_mode() and not request.use_sample
            else None
        ),
        "quality_report": quality_report,
        "ollama_reasoning": ollama_stats,
        "matches": matches,
    }
    _ranking_cache = payload
    return payload


def _persist_submission_from_cache() -> None:
    if not _ranking_cache or not _ranking_cache.get("matches"):
        return
    with open(SUBMISSION_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])
        for m in _ranking_cache["matches"]:
            writer.writerow([m["candidate_id"], m["rank"], m["score"], m["reasoning"]])


@router.post("/matches/{candidate_id}/reasoning")
async def generate_match_reasoning(candidate_id: str):
    """On-demand Ollama reasoning for a single ranked candidate (~3–5s)."""
    global _ranking_cache

    if not _ranking_cache:
        raise HTTPException(status_code=404, detail="Run ranking first.")
    if not is_ollama_available():
        raise HTTPException(status_code=503, detail="Ollama not running. Start with: ollama serve")

    match = next(
        (m for m in _ranking_cache["matches"] if m["candidate_id"] == candidate_id),
        None,
    )
    if match is None:
        raise HTTPException(status_code=404, detail="Candidate not in current rankings.")

    use_sample = _ranking_cache.get("pool") == "sample"
    try:
        path = get_candidates_path(use_sample=use_sample)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    candidate = find_candidate_by_id(path, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate profile not found in pool.")

    breakdown = match.get("score_breakdown") or {}
    audit = match.get("audit") or {}
    rank = int(match["rank"])

    llm_text = generate_ollama_reasoning(
        candidate,
        breakdown,
        audit,
        rank,
        rule_based=match.get("reasoning"),
        timeout=30,
    )
    if not llm_text:
        raise HTTPException(status_code=504, detail="Ollama reasoning failed or timed out.")

    match["reasoning"] = llm_text
    match["reasoning_source"] = "ollama"
    _persist_submission_from_cache()

    return {
        "candidate_id": candidate_id,
        "rank": rank,
        "reasoning": llm_text,
        "reasoning_source": "ollama",
    }


@router.get("/rankings")
async def get_cached_rankings(limit: int = Query(default=100, le=100)):
    if not _ranking_cache:
        raise HTTPException(status_code=404, detail="No rankings yet. POST /api/v1/challenge/rank first.")
    return {
        "job": _ranking_cache["job"],
        "pool": _ranking_cache["pool"],
        "quality_report": _ranking_cache.get("quality_report"),
        "matches": _ranking_cache["matches"][:limit],
    }


@router.get("/audit")
async def get_audit_report():
    if not _ranking_cache:
        raise HTTPException(status_code=404, detail="Run ranking first.")
    return audit_ranking(_ranking_cache["matches"])


@router.get("/export-csv")
async def export_submission_csv():
    if not _ranking_cache or not _ranking_cache.get("matches"):
        raise HTTPException(status_code=404, detail="Run ranking first.")

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["candidate_id", "rank", "score", "reasoning"])
    for m in _ranking_cache["matches"]:
        writer.writerow([m["candidate_id"], m["rank"], m["score"], m["reasoning"]])

    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=submission.csv"},
    )
