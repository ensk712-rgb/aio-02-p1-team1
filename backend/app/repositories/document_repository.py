"""`documents` 테이블(pgvector) 접근 전담입니다.

이 테이블은 04_rag 실습에서도 함께 쓰는 공용 테이블이라, `collection_name`을
`settings.ranger_collection`으로 고정해 다른 Lab의 데이터와 섞이지 않게 합니다.
RAG 정책(임계값, top_k)은 여기 두지 않고 `services/rag_service.py`가 갖습니다.
"""

import json
from contextlib import contextmanager
from uuid import uuid4

import psycopg
from pgvector import Vector
from pgvector.psycopg import register_vector

from app.core.config import settings


@contextmanager
def _connection():
    conn = psycopg.connect(settings.database_url, autocommit=True)
    register_vector(conn)
    try:
        yield conn
    finally:
        conn.close()


def insert_chunks(chunks: list[dict]) -> int:
    """chunk: {title, content, source, chunk_index, embedding, metadata}"""
    with _connection() as conn, conn.cursor() as cur:
        for chunk in chunks:
            cur.execute(
                """
                INSERT INTO documents
                    (id, collection_name, title, content, source, chunk_index,
                     embedding_provider, embedding_model, embedding_dimension, embedding, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    str(uuid4()),
                    settings.ranger_collection,
                    chunk["title"],
                    chunk["content"],
                    chunk["source"],
                    chunk["chunk_index"],
                    "ollama",
                    settings.ollama_embedding_model,
                    len(chunk["embedding"]),
                    Vector(chunk["embedding"]),
                    json.dumps(chunk.get("metadata", {}), ensure_ascii=False),
                ),
            )
    return len(chunks)


def similarity_search(embedding: list[float], top_k: int = 5) -> list[dict]:
    """코사인 거리(`<=>`)가 작은 순으로 top_k를 반환합니다. score는 1 - 거리(클수록 유사)."""
    vector = Vector(embedding)
    with _connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT title, content, source, metadata, 1 - (embedding <=> %s) AS score
            FROM documents
            WHERE collection_name = %s
            ORDER BY embedding <=> %s
            LIMIT %s
            """,
            (vector, settings.ranger_collection, vector, top_k),
        )
        rows = cur.fetchall()
    return [{"title": r[0], "content": r[1], "source": r[2], "metadata": r[3], "score": float(r[4])} for r in rows]


def clear_collection() -> int:
    """재색인 전 기존 chunk를 지웁니다 (`scripts/ingest.py` 전용)."""
    with _connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM documents WHERE collection_name = %s", (settings.ranger_collection,))
        return cur.rowcount
