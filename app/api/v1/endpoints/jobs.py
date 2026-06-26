from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from app.db.session import get_db
from app.schemas.job import Job, JobCreate, JobUpdate
from app.db.models.job import Job as JobModel

router = APIRouter()


@router.post("/", response_model=Job)
async def create_job(
    job_in: JobCreate,
    db: AsyncSession = Depends(get_db)
):
    # TODO: Get owner_id from authentication
    job = JobModel(**job_in.model_dump(), owner_id=1)
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    return job


@router.get("/", response_model=List[Job])
async def list_jobs(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(JobModel).offset(skip).limit(limit)
    )
    jobs = result.scalars().all()
    return jobs


@router.get("/{job_id}", response_model=Job)
async def get_job(
    job_id: int,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(JobModel).where(JobModel.id == job_id)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job


@router.put("/{job_id}", response_model=Job)
async def update_job(
    job_id: int,
    job_update: JobUpdate,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(JobModel).where(JobModel.id == job_id)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    update_data = job_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(job, field, value)
    
    await db.commit()
    await db.refresh(job)
    return job


@router.delete("/{job_id}")
async def delete_job(
    job_id: int,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(JobModel).where(JobModel.id == job_id)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    await db.delete(job)
    await db.commit()
    return {"message": "Job deleted successfully"}
