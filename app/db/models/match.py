from sqlalchemy import Column, String, Float, JSON, ForeignKey
from sqlalchemy.orm import relationship
from app.db.models.base import BaseMixin
from app.db.base import Base


class Match(Base, BaseMixin):
    __tablename__ = "matches"
    
    score = Column(Float, nullable=False)
    analysis = Column(JSON)
    skill_match_score = Column(Float)
    experience_match_score = Column(Float)
    education_match_score = Column(Float)
    notes = Column(String)
    
    candidate_id = Column(Integer, ForeignKey("candidates.id"))
    candidate = relationship("Candidate", back_populates="matches")
    
    job_id = Column(Integer, ForeignKey("jobs.id"))
    job = relationship("Job", back_populates="matches")
