from sqlalchemy import Column, String, Text, Float, JSON, ForeignKey, Enum, Boolean, Integer, DateTime
from sqlalchemy.orm import relationship
import enum
from datetime import datetime
from app.db.base import Base


class JobStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    CLOSED = "closed"


class Job(Base):
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    requirements = Column(JSON)
    skills = Column(JSON)
    min_experience_years = Column(Float, default=0)
    salary_min = Column(Float)
    salary_max = Column(Float)
    location = Column(String)
    remote = Column(Boolean, default=False)
    status = Column(Enum(JobStatus), default=JobStatus.DRAFT)
    embedding = Column(JSON)
    owner_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    owner = relationship("User", back_populates="jobs")
    matches = relationship("Match", back_populates="job")
