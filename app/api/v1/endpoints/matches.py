from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from app.db.session import get_db
from app.schemas.match import Match, MatchCreate
from app.db.models.match import Match as MatchModel
from app.services.matcher import find_best_matches, generate_candidate_embedding, generate_job_embedding
from app.db.models.candidate import Candidate
from app.db.models.job import Job

router = APIRouter()


@router.post("/", response_model=Match)
async def create_match(
    match_in: MatchCreate,
    db: AsyncSession = Depends(get_db)
):
    match = MatchModel(**match_in.model_dump())
    db.add(match)
    await db.commit()
    await db.refresh(match)
    
    return match


@router.get("/job/{job_id}/find-best")
async def find_best_candidates_for_job(
    job_id: int,
    limit: int = 10,
    db: AsyncSession = Depends(get_db)
):
    """Find the best matching candidates for a job using AI analysis."""
    matches = await find_best_matches(job_id, db, limit)
    return {"job_id": job_id, "matches": matches}


@router.post("/candidate/{candidate_id}/generate-embedding")
async def generate_candidate_embedding_endpoint(
    candidate_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Generate and store embedding for a candidate."""
    result = await db.execute(
        select(Candidate).where(Candidate.id == candidate_id)
    )
    candidate = result.scalar_one_or_none()
    
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    embedding = await generate_candidate_embedding(candidate)
    candidate.embedding = embedding
    await db.commit()
    
    return {"message": "Embedding generated successfully"}


@router.post("/job/{job_id}/generate-embedding")
async def generate_job_embedding_endpoint(
    job_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Generate and store embedding for a job."""
    result = await db.execute(
        select(Job).where(Job.id == job_id)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    embedding = await generate_job_embedding(job)
    job.embedding = embedding
    await db.commit()
    
    return {"message": "Embedding generated successfully"}


@router.get("/job/{job_id}", response_model=List[Match])
async def get_matches_for_job(
    job_id: int,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(MatchModel).where(MatchModel.job_id == job_id)
    )
    matches = result.scalars().all()
    return matches


@router.get("/candidate/{candidate_id}", response_model=List[Match])
async def get_matches_for_candidate(
    candidate_id: int,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(MatchModel).where(MatchModel.candidate_id == candidate_id)
    )
    matches = result.scalars().all()
    return matches


@router.get("/{match_id}", response_model=Match)
async def get_match(
    match_id: int,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(MatchModel).where(MatchModel.id == match_id)
    )
    match = result.scalar_one_or_none()
    
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    
    return match
