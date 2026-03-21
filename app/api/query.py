from fastapi import APIRouter, Depends
from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.config import OPENAI_API_KEY
from app.db.database import get_db

router = APIRouter(prefix="/query")

client = OpenAI(api_key=OPENAI_API_KEY)

@router.post("")
def query(question: str, db: Session = Depends(get_db)):
    query_embeddings = client.embeddings.create(
        model="text-embedding-3-small",
        input=question
    )

    query_vector = query_embeddings.data[0].embedding

    print(len(query_vector))

    context = """
    function createUser(user) {
        return db.save(user)
    }
    """

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
        "answer": response.choices[0].message.content
    }