from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class JobStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    CLOSED = "closed"


class JobBase(BaseModel):
    title: str
    description: str
    requirements: Optional[List[str]] = None
    skills: Optional[List[str]] = None
    min_experience_years: Optional[float] = 0
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    location: Optional[str] = None
    remote: bool = False
    status: JobStatus = JobStatus.DRAFT


class JobCreate(JobBase):
    pass


class JobUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[List[str]] = None
    skills: Optional[List[str]] = None
    min_experience_years: Optional[float] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    location: Optional[str] = None
    remote: Optional[bool] = None
    status: Optional[JobStatus] = None


class JobInDB(JobBase):
    id: int
    owner_id: int
    embedding: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class Job(JobInDB):
    pass
