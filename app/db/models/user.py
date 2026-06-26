from sqlalchemy import Column, String, Boolean, Text
from sqlalchemy.orm import relationship
from app.db.models.base import BaseMixin
from app.db.base import Base


class User(Base, BaseMixin):
    __tablename__ = "users"
    
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    company = Column(String)
    role = Column(String, default="recruiter")
    
    jobs = relationship("Job", back_populates="owner")
