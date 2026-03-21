from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Repo

router = APIRouter(prefix="/repos")

@router.post("")
def create_repo(repo_url: str, db: Session = Depends(get_db)):
    repo = Repo(
        repo_url=repo_url,
        status="PENDING"
    )

    db.add(repo)
    db.commit()
    db.refresh(repo)

    return {
        "repo_id": repo.id,
        "status": repo.status
    }