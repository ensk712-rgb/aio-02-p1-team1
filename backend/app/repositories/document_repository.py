"""동물 정보카드 저장소 + 키워드 검색 (최두나 소유, 작업지시서 v1.1 4.3절).

- 카드당 한 Chunk로 시작한다 (PDF 분할기·임베딩 서비스 없음).
- 점수는 임베딩 유사도가 아니라 "정규화된 검색 토큰 중 카드 본문·키워드와
  겹친 토큰의 비율"이다 (0~1). 같은 점수면 doc_id 오름차순 정렬.
- 조사·질문 표현을 제외하는 작은 정규화 규칙을 둔다 (완전한 형태소 분석이 아님).
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from backend.app.core.config import DATA_DIR, try_get_settings
from backend.app.schemas.common import RetrievedChunk
from backend.app.schemas.tools import ChunkInput

# 길이가 긴 것부터 먼저 검사해야 부분 중복(예: "에서"가 "가"보다 먼저)을 피한다.
_PARTICLE_SUFFIXES = sorted(
    ["에서", "에게", "한테", "이랑", "까지", "부터", "이는", "는", "이", "가", "을", "를", "의", "도", "만", "과", "와", "랑"],
    key=len,
    reverse=True,
)

# 검색 의미가 없는 질문 표현·조동사류. 정규화 후 이 목록에 해당하면 토큰에서 제외한다.
_STOPWORDS = {
    "어디", "무엇", "뭐", "언제", "몇", "어떻게", "어떤", "알려줘", "줘", "해줘", "좀",
    "살고", "살아", "살아요", "있어", "있나요", "인가요", "이야", "야", "해요", "돼",
    "되나요", "왔어", "왔", "이고", "그", "이", "저",
}

# 자주 쓰이는 동사 활용형을 카드 키워드의 canonical 형태로 매핑한다.
_SYNONYMS = {
    "먹어": "먹이", "먹나": "먹이", "먹니": "먹이", "먹는": "먹이", "먹지": "먹이",
    "산다": "서식", "사나": "서식",
}


def _strip_particle(word: str) -> str:
    for suffix in _PARTICLE_SUFFIXES:
        if word.endswith(suffix) and len(word) > len(suffix):
            return word[: -len(suffix)]
    return word


def _tokenize(text: str) -> list[str]:
    cleaned = re.sub(r"[?!.,~]", " ", text)
    tokens: list[str] = []
    for raw_word in cleaned.split():
        root = _strip_particle(raw_word)
        root = _SYNONYMS.get(root, root)
        if not root or root in _STOPWORDS:
            continue
        tokens.append(root)
    return tokens


@lru_cache
def load_cards() -> tuple[dict, ...]:
    """data/animal_cards/*.json을 전부 읽어 카드 dict 튜플로 반환한다."""
    cards_dir: Path = DATA_DIR / "animal_cards"
    cards = []
    for path in sorted(cards_dir.glob("*.json")):
        with path.open(encoding="utf-8") as f:
            cards.append(json.load(f))
    return tuple(cards)


def _score(tokens: list[str], card: dict) -> float:
    if not tokens:
        return 0.0
    keywords = set(card["keywords"])
    text = card["text"]
    matched = sum(1 for token in tokens if token in keywords or token in text)
    return round(matched / len(tokens), 4)


def _search_memory(query: str, collection: str, top_k: int) -> list[RetrievedChunk]:
    """기존 키워드 매칭 검색 (STORAGE_MODE=memory)."""
    tokens = _tokenize(query)
    scored: list[tuple[float, dict]] = []
    for card in load_cards():
        if card["collection"] != collection:
            continue
        scored.append((_score(tokens, card), card))

    # 점수 내림차순, 동점이면 doc_id 오름차순
    scored.sort(key=lambda pair: (-pair[0], pair[1]["doc_id"]))

    return [
        RetrievedChunk(
            doc_id=card["doc_id"],
            title=card["title"],
            page=card.get("page"),
            text=card["text"],
            score=score,
            collection=card["collection"],
        )
        for score, card in scored[:top_k]
    ]


def _search_persistent(query: str, collection: str, top_k: int) -> list[RetrievedChunk]:
    """pgvector 코사인 유사도 검색 (STORAGE_MODE=persistent)."""
    import asyncio

    from backend.app.core.db import get_connection_pool
    from backend.app.services.embedding_service import embed_text

    query_embedding = asyncio.run(embed_text(query))
    pool = get_connection_pool()

    with pool.connection() as conn:
        rows = conn.execute(
            """
            SELECT
                doc_id,
                title,
                page,
                text,
                collection,
                (embedding <=> %s::vector) AS distance,
                CASE
                    WHEN POSITION(LOWER(title) IN LOWER(%s)) > 0 THEN 1.0
                    WHEN EXISTS (
                        SELECT 1
                        FROM unnest(keywords) AS keyword
                        WHERE char_length(keyword) >= 2
                          AND POSITION(LOWER(keyword) IN LOWER(%s)) > 0
                    ) THEN 0.8
                    ELSE 0.0
                END AS lexical_score
            FROM document_chunks
            WHERE collection = %s
            ORDER BY
                lexical_score DESC,
                embedding <=> %s::vector,
                doc_id ASC
            LIMIT %s
            """,
            (
                query_embedding,
                query,
                query,
                collection,
                query_embedding,
                top_k,
            ),
        ).fetchall()

    return [
        RetrievedChunk(
            doc_id=row[0],
            title=row[1],
            page=row[2],
            text=row[3],
            collection=row[4],
            score=round(
                max(
                    float(row[6]),
                    1.0 - float(row[5]),
                ),
                4,
            ),
        )
        for row in rows
    ]


def search(query: str, collection: str, top_k: int) -> list[RetrievedChunk]:
    """STORAGE_MODE에 따라 키워드 검색 또는 pgvector 검색으로 분기한다."""
    settings = try_get_settings()
    if settings is not None and settings.STORAGE_MODE == "persistent":
        return _search_persistent(query, collection, top_k)
    return _search_memory(query, collection, top_k)


def insert_chunks(chunks: list[ChunkInput]) -> None:
    """청크 목록을 임베딩해 pgvector 테이블에 upsert한다 (STORAGE_MODE=persistent 전용).

    PDF 업로드(서브프로젝트 2)와 시딩 스크립트가 이 함수를 사용한다.
    """
    import asyncio

    from backend.app.core.db import get_connection_pool
    from backend.app.services.embedding_service import embed_text

    pool = get_connection_pool()
    with pool.connection() as conn:
        for chunk in chunks:
            embedding = asyncio.run(embed_text(chunk.text))
            conn.execute(
                """
                INSERT INTO document_chunks
                    (doc_id, collection, title, page, text, keywords, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s::vector)
                ON CONFLICT (doc_id, collection) DO UPDATE SET
                    title = EXCLUDED.title,
                    page = EXCLUDED.page,
                    text = EXCLUDED.text,
                    keywords = EXCLUDED.keywords,
                    embedding = EXCLUDED.embedding
                """,
                (
                    chunk.doc_id,
                    chunk.collection,
                    chunk.title,
                    chunk.page,
                    chunk.text,
                    chunk.keywords,
                    embedding,
                ),
            )
        conn.commit()
