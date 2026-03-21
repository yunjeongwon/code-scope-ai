from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from app.db.database import Base

class Repo(Base):
    __tablename__ = "repos"

    id = Column(Integer, primary_key=True, index=True)
    repo_url = Column(String, nullable=False)
    status = Column(String, default="PENDING")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

