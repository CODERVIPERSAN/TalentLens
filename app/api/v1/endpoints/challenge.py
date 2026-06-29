from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.challenge_data import (
    get_candidates_path,
    get_job,
    pool_info,
)
from app.services.challenge_ranker import load_candidates, rank_candidates

router = APIRouter()

_ranking_cache: dict[str, Any] | None = None


class RankingRequest(BaseModel):
    use_sample: bool = True
    top_n: int = Field(default=50, ge=1, le=100)


class RankingResult(BaseModel):
    candidate_id: str
    rank: int
    score: float
    reasoning: str
    profile_summary: dict[str, Any]
    score_breakdown: dict[str, float] = {}


class RankingResponse(BaseModel):
    job: dict[str, Any]
    pool: str
    pool_size: int
    ranked_count: int
    matches: list[RankingResult]


def _serialize_match(r) -> dict[str, Any]:
    return {
        "candidate_id": r.candidate_id,
        "rank": r.rank,
        "score": r.score,
        "reasoning": r.reasoning,
        "profile_summary": r.profile_summary,
        "score_breakdown": r.score_breakdown,
    }


@router.get("/stats")
async def get_challenge_stats():
    job = get_job()
    pools = pool_info()
    return {
        "sample_candidates": pools["sample_count"],
        "full_pool_size": pools["full_count"] or 100000,
        "job_title": job["title"],
        "company": job["company"],
        "ranking_ready": pools["sample_available"] or pools["full_available"],
        "full_pool_available": pools["full_available"],
    }


@router.get("/job")
async def get_challenge_job():
    return get_job()


@router.get("/candidates")
async def list_challenge_candidates(
    skip: int = 0,
    limit: int = 50,
    use_sample: bool = True,
):
    try:
        path = get_candidates_path(use_sample=use_sample)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    candidates = load_candidates(path)
    page = candidates[skip : skip + limit]

    return {
        "pool": "sample" if use_sample else "full",
        "total": len(candidates),
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

    for candidate in load_candidates(path):
        if candidate["candidate_id"] == candidate_id:
            return candidate
    raise HTTPException(status_code=404, detail="Candidate not found")


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

    candidates = load_candidates(path)
    top_n = min(request.top_n, len(candidates), 100)
    results = rank_candidates(candidates, job_description, top_n=top_n)
    matches = [_serialize_match(r) for r in results]

    payload = {
        "job": {
            "job_id": job.get("job_id"),
            "title": job["title"],
            "company": job["company"],
            "location": job["location"],
            "experience_range": job.get("experience_range"),
        },
        "pool": "sample" if request.use_sample else "full",
        "pool_size": len(candidates),
        "ranked_count": len(matches),
        "matches": matches,
    }
    _ranking_cache = payload
    return payload


@router.get("/rankings")
async def get_cached_rankings(limit: int = Query(default=100, le=100)):
    if not _ranking_cache:
        raise HTTPException(
            status_code=404,
            detail="No rankings yet. POST /api/v1/challenge/rank first.",
        )
    return {
        "job": _ranking_cache["job"],
        "pool": _ranking_cache["pool"],
        "matches": _ranking_cache["matches"][:limit],
    }
