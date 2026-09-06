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

from backend.app.core.config import DATA_DIR
from backend.app.schemas.common import RetrievedChunk

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


def search(query: str, collection: str, top_k: int) -> list[RetrievedChunk]:
    """query와 각 카드의 겹침 비율로 점수를 매겨 상위 top_k Chunk를 반환한다."""
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
