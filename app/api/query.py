from fastapi import APIRouter, Depends
from openai import OpenAI
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

    results = (
        db.query(CodeChunk)
            .where(CodeChunk.repo_id == repo_id)
            .order_by(CodeChunk.embedding.l2_distance(query_vector))
            .limit(3)
            .all()
    )

    references = []
    context_parts = []

    for chunk in results:
        references.append({
            "file_path": chunk.file_path,
            "function_name": chunk.function_name,
            "start_line": chunk.start_line,
            "end_line": chunk.end_line,
        })

        context_parts.append(f"""
            파일: {chunk.file_path}
            함수: {chunk.function_name}

            {chunk.content}
            """)

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

class QueryRequest:
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