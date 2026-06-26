from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from app.db.session import get_db
from app.schemas.candidate import Candidate, CandidateCreate, CandidateUpdate
from app.db.models.candidate import Candidate as CandidateModel

router = APIRouter()


@router.post("/", response_model=Candidate)
async def create_candidate(
    candidate_in: CandidateCreate,
    db: AsyncSession = Depends(get_db)
):
    # Check if candidate exists
    result = await db.execute(
        select(CandidateModel).where(CandidateModel.email == candidate_in.email)
    )
    existing_candidate = result.scalar_one_or_none()
    
    if existing_candidate:
        raise HTTPException(status_code=400, detail="Candidate with this email already exists")
    
    candidate = CandidateModel(**candidate_in.model_dump())
    db.add(candidate)
    await db.commit()
    await db.refresh(candidate)
    
    return candidate


@router.get("/", response_model=List[Candidate])
async def list_candidates(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(CandidateModel).offset(skip).limit(limit)
    )
    candidates = result.scalars().all()
    return candidates


@router.get("/{candidate_id}", response_model=Candidate)
async def get_candidate(
    candidate_id: int,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(CandidateModel).where(CandidateModel.id == candidate_id)
    )
    candidate = result.scalar_one_or_none()
    
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    return candidate


@router.put("/{candidate_id}", response_model=Candidate)
async def update_candidate(
    candidate_id: int,
    candidate_update: CandidateUpdate,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(CandidateModel).where(CandidateModel.id == candidate_id)
    )
    candidate = result.scalar_one_or_none()
    
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    update_data = candidate_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(candidate, field, value)
    
    await db.commit()
    await db.refresh(candidate)
    return candidate


@router.delete("/{candidate_id}")
async def delete_candidate(
    candidate_id: int,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(CandidateModel).where(CandidateModel.id == candidate_id)
    )
    candidate = result.scalar_one_or_none()
    
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    await db.delete(candidate)
    await db.commit()
    return {"message": "Candidate deleted successfully"}
