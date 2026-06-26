from sqlalchemy import Column, String, Text, Float, JSON, Integer, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base import Base


class Candidate(Base):
    __tablename__ = "candidates"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    phone = Column(String)
    resume_text = Column(Text)
    skills = Column(JSON)
    experience_years = Column(Float, default=0)
    education = Column(JSON)
    embedding = Column(JSON)
    location = Column(String)
    linkedin_url = Column(String)
    github_url = Column(String)
    portfolio_url = Column(String)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    matches = relationship("Match", back_populates="candidate")
