from fastapi import APIRouter, Depends
from openai import OpenAI
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import OPENAI_API_KEY
from app.db.database import get_db
from app.db.models import CodeChunk

router = APIRouter(prefix="/query")

client = OpenAI(api_key=OPENAI_API_KEY)

@router.post("")
def query(queryRequest: QueryRequest, db: Session = Depends(get_db)):
    # insert_test_chunk(db)

    repo_id = queryRequest.repo_id
    question = queryRequest.question

    query_embeddings = client.embeddings.create(
        model="text-embedding-3-small",
        input=question
    )

    query_vector = query_embeddings.data[0].embedding

    query = db.query(CodeChunk)

    query = query.filter(CodeChunk.repo_id == repo_id)
    query = query.filter(CodeChunk.function_name.isnot(None))

    STOP_WORD = {"어디야", "뭐야", "어떻게", "해줘", "알려줘"}

    keywords = [
        k for k in question.lower().split() if k not in STOP_WORD
    ]

    KEYWORD_MAP = {
        "생성": "create",
        "유저": "user",
        "삭제": "delete",
        "조회": "get",
    }

    processed_keywords = []

    for k in keywords:
        if k in KEYWORD_MAP:
            processed_keywords.append(KEYWORD_MAP[k])
        else:
            processed_keywords.append(k)

    conditions = [
        CodeChunk.function_name.ilike(f"%{k}%")
        for k in processed_keywords
    ]

    if conditions:
        query = query.filter(or_(*conditions))


    # vector
    results = (
        query
            .order_by(CodeChunk.embedding.l2_distance(query_vector))
            .limit(3)
            .all()
    )

    # score 혼합
    candidates = results

    def score_chunk(chunk):
        score = 0
        for k in processed_keywords:
            if chunk.function_name and k in chunk.function_name:
                score += 2
            
            if k in chunk.content:
                score += 1

        return score

    reranked = sorted(candidates, key=score_chunk, reverse=True)

    top_results = reranked[:3]

    references = []
    context_parts = []

    for chunk in top_results:
        references.append({
            "content": chunk.content,
            "start_line": chunk.start_line,
            "end_line": chunk.end_line,
            "file_path": chunk.file_path,
            "function_name": chunk.function_name,
            "class_name": chunk.class_name,
            "chunk_type": chunk.chunk_type,
            "language": chunk.language,
        })

        context_parts.append(f"파일: {chunk.file_path}\n함수: {chunk.function_name}\n\n{chunk.content}")

    context = "\n".join(context_parts)

    prompt = f"""
    다음 코드를 참고해서 질문에 답해라.
    [CODE]
    {context}

    [QUESTION]
    {question}
    """

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": "You are a backend expert."},
            {"role": "user", "content": prompt},
        ]
    )

    return {
        "answer": response.choices[0].message.content,
        "references": references
    }

class QueryRequest(BaseModel):
    repo_id: int
    question: str

def insert_test_chunk(db: Session):
    code = """
    def create_user(user):
        return db.save(user)
    """

    embeddings_response = client.embeddings.create(
        model="text-embedding-3-small",
        input=code
    )

    vector = embeddings_response.data[0].embedding

    chunk = CodeChunk(
        repo_id=1,
        content=code,
        embedding=vector,
        file_path="user_service.py",
        function_name="create_user",
        language="python",
        start_line=1,
        end_line=3
    )

    db.add(chunk)
    db.commit()