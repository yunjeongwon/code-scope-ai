import os
import subprocess
from fastapi import APIRouter, Depends, BackgroundTasks
from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.config import OPENAI_API_KEY
from app.db.database import get_db
from app.db.models import CodeChunk, Repo

router = APIRouter(prefix="/repos")

client = OpenAI(api_key=OPENAI_API_KEY)

@router.post("")
def create_repo(
    repo_url: str, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    repo = Repo(
        repo_url=repo_url,
        status="PENDING"
    )

    db.add(repo)
    db.commit()
    db.refresh(repo)

    # ingest_repo(repo.id, repo.repo_url, db)

    background_tasks.add_task(ingest_repo, repo.id, repo.repo_url)

    return {
        "repo_id": repo.id,
        "status": repo.status
    }

@router.get("/{repo_id}")
def get_repo(repo_id: int, db: Session = Depends(get_db)):
    repo = db.query(Repo).filter(Repo.id == repo_id).first()

    if not repo:
        return {
            "error": "Repo not found"
        }
    return {
        "repo_id": repo.id,
        "repo_url": repo.repo_url,
        "status": repo.status,
    }

def ingest_repo(repo_id: int, repo_url: str):
    repo = None

    try:
        db = next(get_db())

        repo = db.query(Repo).filter(Repo.id == repo_id).first()
        repo.status = "PROCESSING"
        db.commit()

        repo_path = f"/tmp/repos/{repo_id}"

        if os.path.exists(repo_path) and os.listdir(repo_path):
            return

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

                def get_chunk_type(line: str):
                    stripped = line.strip()

                    if stripped.startswith("def "):
                        return "function"

                    if stripped.startswith("class "):
                        return "class"
                    
                    return None

                def extract_name(line: str, chunk_type: str):
                    line = line.strip()

                    if chunk_type == "function":
                        return line.split("(")[0].replace("def", "").strip()

                    if chunk_type == "class":
                        return line.split("(")[0].replace("class", "").strip()
                    
                    return None

                lines = content.split("\n")

                chunks = []
                current_chunk = []
                start_line = 1
                current_class = None

                for idx, line in enumerate(lines):
                    chunk_type = get_chunk_type(line)

                    if chunk_type and current_chunk:
                        first_line = current_chunk[0]
                        first_type = get_chunk_type(first_line)

                        chunks.append({
                            "content": "\n".join(current_chunk),
                            "start_line": start_line,
                            "end_line": idx,
                            "file_path": file_path,
                            "function_name": extract_name(first_line, first_type) if first_type == "function" else None,
                            "class_name": current_class,
                            "chunk_type": first_type
                        })

                        current_chunk = []
                        start_line =  idx + 1
                    
                    if chunk_type == "class":
                        current_class = extract_name(line, "class")
                    
                    current_chunk.append(line)
                
                if current_chunk:
                    first_line = current_chunk[0]
                    first_type = get_chunk_type(first_line)

                    chunks.append({
                        "content": "\n".join(current_chunk),
                        "start_line": start_line,
                        "end_line": len(lines),
                        "file_path": file_path,
                        "function_name": extract_name(first_line, first_type) if first_type == "function" else None,
                        "class_name": current_class,
                        "chunk_type": first_type
                    })

                for chunk in chunks:
                    if not chunk["function_name"] and not chunk["class_name"]:
                        continue

                    embedding_response = client.embeddings.create(
                        model="text-embedding-3-small",
                        input=chunk["content"]
                    )

                    vector = embedding_response.data[0].embedding

                    codeChunk = CodeChunk(
                        repo_id=repo_id,
                        embedding=vector,
                        content=chunk["content"],
                        start_line=chunk["start_line"],
                        end_line=chunk["end_line"],
                        file_path=chunk["file_path"],
                        function_name=chunk["function_name"],
                        class_name=chunk["class_name"],
                        chunk_type=chunk["chunk_type"],
                        language=file.split(".")[-1],
                    )

                    db.add(codeChunk)

        repo.status = "DONE"
        db.commit()

    except Exception as e:
        print("ERROR:", e)
        if repo:
            repo.status = "FAILED"

        db.commit()
    finally:
        db.close()