from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.challenge_ranker import load_candidates, rank_candidates

router = APIRouter()

DATA_DIR = Path(__file__).resolve().parents[4] / "data"
SAMPLE_CANDIDATES = DATA_DIR / "sample_candidates.json"
JOB_DESCRIPTION = DATA_DIR / "job_description.txt"

_ranking_cache: list[dict[str, Any]] | None = None


class RankingRequest(BaseModel):
    use_sample: bool = True
    top_n: int = 100


class RankingResult(BaseModel):
    candidate_id: str
    rank: int
    score: float
    reasoning: str
    profile_summary: dict[str, Any]


@router.get("/stats")
async def get_challenge_stats():
    sample_count = 0
    if SAMPLE_CANDIDATES.exists():
        candidates = load_candidates(SAMPLE_CANDIDATES)
        sample_count = len(candidates)

    return {
        "sample_candidates": sample_count,
        "full_pool_size": 100000,
        "job_title": "Senior AI Engineer — Founding Team",
        "company": "Redrob AI",
        "ranking_ready": SAMPLE_CANDIDATES.exists() and JOB_DESCRIPTION.exists(),
    }


@router.get("/candidates")
async def list_challenge_candidates(
    skip: int = 0,
    limit: int = 50,
):
    if not SAMPLE_CANDIDATES.exists():
        raise HTTPException(status_code=404, detail="Sample candidates not found")

    candidates = load_candidates(SAMPLE_CANDIDATES)
    page = candidates[skip : skip + limit]

    return [
        {
            "candidate_id": c["candidate_id"],
            "name": c.get("profile", {}).get("anonymized_name"),
            "title": c.get("profile", {}).get("current_title"),
            "location": c.get("profile", {}).get("location"),
            "years_of_experience": c.get("profile", {}).get("years_of_experience"),
            "skills": [s.get("name") for s in c.get("skills", [])[:6]],
            "open_to_work": c.get("redrob_signals", {}).get("open_to_work_flag"),
        }
        for c in page
    ]


@router.post("/rank", response_model=list[RankingResult])
async def run_challenge_ranking(request: RankingRequest = RankingRequest()):
    global _ranking_cache

    if not JOB_DESCRIPTION.exists():
        raise HTTPException(status_code=404, detail="Job description not found")

    candidates_path = SAMPLE_CANDIDATES
    if not candidates_path.exists():
        raise HTTPException(status_code=404, detail="Candidate data not found")

    candidates = load_candidates(candidates_path)
    job_description = JOB_DESCRIPTION.read_text(encoding="utf-8")
    top_n = min(request.top_n, len(candidates))

    results = rank_candidates(candidates, job_description, top_n=top_n)
    payload = [
        {
            "candidate_id": r.candidate_id,
            "rank": r.rank,
            "score": r.score,
            "reasoning": r.reasoning,
            "profile_summary": r.profile_summary,
        }
        for r in results
    ]
    _ranking_cache = payload
    return payload


@router.get("/rankings", response_model=list[RankingResult])
async def get_cached_rankings(limit: int = Query(default=100, le=100)):
    if not _ranking_cache:
        raise HTTPException(
            status_code=404,
            detail="No rankings yet. POST /api/v1/challenge/rank first.",
        )
    return _ranking_cache[:limit]
