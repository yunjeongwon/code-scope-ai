import os
from pydoc import cli
import subprocess
from fastapi import APIRouter, Depends
from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.config import OPENAI_API_KEY
from app.db.database import get_db
from app.db.models import CodeChunk, Repo

router = APIRouter(prefix="/repos")

client = OpenAI(api_key=OPENAI_API_KEY)

@router.post("")
def create_repo(repo_url: str, db: Session = Depends(get_db)):
    repo = Repo(
        repo_url=repo_url,
        status="PENDING"
    )

    db.add(repo)
    db.commit()
    db.refresh(repo)

    ingest_repo(repo.id, repo.repo_url, db)

    return {
        "repo_id": repo.id,
        "status": repo.status
    }

def ingest_repo(repo_id: int, repo_url: str, db: Session):
    repo_path = f"/tmp/repos/{repo_id}"

    os.makedirs(repo_path, exist_ok=True)

    subprocess.run(
        ["git", "clone", repo_url, repo_path],
        check=True
    )

    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in [".git", "node_modules", "__pycache__"]]

        for file in files:
            if not file.endswith((".py", ".js", ".ts")):
                continue

            file_path = os.path.join(root, file)

            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            lines = content.split("\n")

            chunk_size = 50

            chunks = []

            for i in range(0, len(lines), chunk_size):
                chunk_lines = lines[i:i+chunk_size]
                chunk_content = "\n".join(chunk_lines)

                if not chunk_content.strip():
                    continue

                chunks.append({
                    "content": chunk_content,
                    "start_line": i + 1,
                    "end_line": i + len(chunk_lines),
                    "file_path": file_path,
                })
            
            for chunk in chunks:
                embedding_response = client.embeddings.create(
                    model="text-embedding-3-small",
                    input=chunk["content"]
                )

                vector = embedding_response.data[0].embedding

                codeChunk = CodeChunk(
                    repo_id=repo_id,
                    content=chunk["content"],
                    embedding=vector,
                    file_path=chunk["file_path"],
                    start_line=chunk["start_line"],
                    end_line=chunk["end_line"],
                    language=file.split(",")[-1]
                )

                db.add(codeChunk)

            db.commit()

