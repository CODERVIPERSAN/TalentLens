from sqlalchemy import Column, String, Text, Float, JSON, ForeignKey, Enum, Boolean
from sqlalchemy.orm import relationship
import enum
from app.db.models.base import BaseMixin
from app.db.base import Base


class JobStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    CLOSED = "closed"


class Job(Base, BaseMixin):
    __tablename__ = "jobs"
    
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
    owner = relationship("User", back_populates="jobs")
    
    matches = relationship("Match", back_populates="job")
