from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


class MatchBase(BaseModel):
    score: float
    analysis: Optional[Dict[str, Any]] = None
    skill_match_score: Optional[float] = None
    experience_match_score: Optional[float] = None
    education_match_score: Optional[float] = None
    notes: Optional[str] = None


class MatchCreate(MatchBase):
    candidate_id: int
    job_id: int


class MatchInDB(MatchBase):
    id: int
    candidate_id: int
    job_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class Match(MatchInDB):
    pass
