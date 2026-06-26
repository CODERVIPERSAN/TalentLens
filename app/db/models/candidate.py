from sqlalchemy import Column, String, Text, Float, JSON, ForeignKey
from sqlalchemy.orm import relationship
from app.db.models.base import BaseMixin
from app.db.base import Base


class Candidate(Base, BaseMixin):
    __tablename__ = "candidates"
    
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
    
    matches = relationship("Match", back_populates="candidate")
