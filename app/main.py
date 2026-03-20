from fastapi import FastAPI
from app.api import repo, query

app = FastAPI()

app.include_router(repo.router)
app.include_router(query.router)

@app.get("/")
def root():
    return {"message": "CodeScope AI"}