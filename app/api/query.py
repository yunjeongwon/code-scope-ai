from fastapi import APIRouter

router = APIRouter(prefix="/query")

@router.post("")
def query():
    return {"message": "query result"}