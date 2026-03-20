from fastapi import APIRouter

router = APIRouter(prefix="/repos")

@router.post("")
def create_repo():
    return {"message": "repo created"}