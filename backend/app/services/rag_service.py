"""문서를 chunk·임베딩해 pgvector에 저장하고, 질문에 근거 기반으로 답합니다.

임베딩은 Ollama `embeddinggemma`(로컬, 무료)를 사용하고, 답변 생성은 공용
Provider(`settings.llm_provider`, 기본 openai)를 사용합니다. 근거가 없으면 지어내지
않고 "모른다"고 답합니다.
"""

import httpx
from pydantic import BaseModel

from app.core.config import settings
from app.providers.registry import get_provider
from app.repositories import document_repository

NO_EVIDENCE_ANSWER = "죄송해요, 지금 갖고 있는 자료로는 확인할 수 없는 내용이에요."


class Chunk(BaseModel):
    title: str
    content: str
    source: str
    chunk_index: int
    metadata: dict = {}


def chunk_document(raw_text: str, title: str, source: str) -> list[Chunk]:
    """빈 줄 기준으로 문단을 나눕니다 — MVP 수준의 단순 chunker입니다."""
    paragraphs = [p.strip() for p in raw_text.split("\n\n") if p.strip() and not p.strip().startswith("# ")]
    return [Chunk(title=title, content=p, source=source, chunk_index=i) for i, p in enumerate(paragraphs)]


def embed_text(text: str) -> list[float]:
    response = httpx.post(
        f"{settings.ollama_base_url}/api/embeddings",
        json={"model": settings.ollama_embedding_model, "prompt": text},
        timeout=settings.request_timeout_seconds,
    )
    response.raise_for_status()
    return response.json()["embedding"]


def embed_and_store(chunks: list[Chunk]) -> int:
    rows = [
        {
            "title": c.title,
            "content": c.content,
            "source": c.source,
            "chunk_index": c.chunk_index,
            "embedding": embed_text(c.content),
            "metadata": c.metadata,
        }
        for c in chunks
    ]
    return document_repository.insert_chunks(rows)


def retrieve_chunks(query: str, top_k: int = 5) -> list[dict]:
    embedding = embed_text(query)
    results = document_repository.similarity_search(embedding, top_k=top_k)
    return [r for r in results if r["score"] >= settings.rag_min_score]


class _RagAnswer(BaseModel):
    answer: str
    used_titles: list[str] = []


_INSTRUCTIONS = (
    "너는 동물원 안내 도우미야. 아래 근거 문서에 있는 내용만 사용해서 한국어로 2~3문장 이내로 "
    "답해. 근거에 없는 내용은 절대 추측하지 말고 모른다고 말해. 실제로 답변에 사용한 문서의 "
    "title만 used_titles에 정확히 그대로 담아."
)


def answer_with_citations(question: str, chunks: list[dict]) -> dict:
    if not chunks:
        return {"answer": NO_EVIDENCE_ANSWER, "sources": []}

    context = "\n\n".join(f"[{i + 1}] ({c['title']} · {c['source']}) {c['content']}" for i, c in enumerate(chunks))
    message = f"질문: {question}\n\n근거 문서:\n{context}"

    result = get_provider(settings.llm_provider).generate_structured(_INSTRUCTIONS, message, _RagAnswer)
    parsed = _RagAnswer.model_validate(result.content)

    by_title = {c["title"]: c for c in chunks}
    sources = [{"title": t, "source": by_title[t]["source"]} for t in parsed.used_titles if t in by_title]
    if not sources:
        sources = [{"title": c["title"], "source": c["source"]} for c in chunks[:2]]
    return {"answer": parsed.answer, "sources": sources}
