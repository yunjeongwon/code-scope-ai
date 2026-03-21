from fastapi import FastAPI
from app.api import repo, query
from app.db.database import Base, engine
from app.db import models

app = FastAPI()

app.include_router(repo.router)
app.include_router(query.router)

Base.metadata.create_all(bind=engine)

@app.get("/")
def root():
    return {"message": "CodeScope AI"}