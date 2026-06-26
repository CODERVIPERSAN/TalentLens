from sqlalchemy import Column, String, Float, JSON, ForeignKey, Integer, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base import Base


class Match(Base):
    __tablename__ = "matches"
    
    id = Column(Integer, primary_key=True, index=True)
    score = Column(Float, nullable=False)
    analysis = Column(JSON)
    skill_match_score = Column(Float)
    experience_match_score = Column(Float)
    education_match_score = Column(Float)
    notes = Column(String)
    candidate_id = Column(Integer, ForeignKey("candidates.id"))
    job_id = Column(Integer, ForeignKey("jobs.id"))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    candidate = relationship("Candidate", back_populates="matches")
    job = relationship("Job", back_populates="matches")
