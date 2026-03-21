from datetime import datetime, timezone
from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from app.db.database import Base

class Repo(Base):
    __tablename__ = "repos"

    id = Column(Integer, primary_key=True, index=True)
    repo_url = Column(String, nullable=False)
    status = Column(String, default="PENDING")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class CodeChunk(Base):
    __tablename__ = "code_chunks"

    id = Column(Integer, primary_key=True, index=True)

    repo_id = Column(Integer, ForeignKey("repos.id"))

    content = Column(String, nullable=False)

    embedding = Column(Vector(1536))

    file_path = Column(String)
    function_name = Column(String)
    language = Column(String)

    start_line = Column(Integer)
    end_line = Column(Integer)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
