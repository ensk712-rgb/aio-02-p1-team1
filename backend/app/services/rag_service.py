"""RAG 준-Tool (최두나 소유, 작업지시서 v1.1 4.3/5장).

- 여기서 별도 LLM을 호출하지 않는다. Runtime이 결과를 LLM에 전달하고
  최종 답변을 만든다 — 근거 생성/사실 판단은 이 서비스의 책임이 아니다.
- RAG_MIN_SCORE 미만 Chunk는 결과에 포함하지 않는다 (LLM 근거에서 제외).
- 결과 없음은 success=true, data={"matched": false, "chunks": []}.
  검색 자체가 실패한 경우만 success=false로 구분한다.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from backend.app.core.config import try_get_settings
from backend.app.repositories.document_repository import search
from backend.app.schemas.common import RetrievedChunk, ToolError, ToolRunResult

SOURCE_NAME = "rag_animal_cards"
_SEOUL = ZoneInfo("Asia/Seoul")

_DEFAULT_TOP_K = 3
_DEFAULT_MIN_SCORE = 0.5


def _resolve_now() -> datetime:
    settings = try_get_settings()
    if settings is not None:
        demo_now = settings.demo_now_datetime()
        if demo_now is not None:
            return demo_now
    return datetime.now(_SEOUL)


def _resolve_thresholds() -> tuple[int, float]:
    settings = try_get_settings()
    if settings is not None:
        return settings.RAG_TOP_K, settings.RAG_MIN_SCORE
    return _DEFAULT_TOP_K, _DEFAULT_MIN_SCORE


def retrieve_chunks(
    query: str, *, collection: str = "animal_cards", top_k: int | None = None
) -> list[RetrievedChunk]:
    """RAG_MIN_SCORE 필터 없이, 점수순 상위 top_k Chunk를 그대로 반환한다."""
    if top_k is None:
        top_k, _ = _resolve_thresholds()
    return search(query, collection, top_k)


def answer_with_citations(question: str, chunks: list[RetrievedChunk]) -> ToolRunResult:
    """이미 채택된(RAG_MIN_SCORE 이상) Chunk만으로 RagSearchData 봉투를 만든다.

    실제 최종 답변 생성(문장 조합)은 Runtime의 Provider 몫이다. 이 함수는
    RAG 결과를 ToolRunResult 계약으로 포장하는 역할만 한다.
    """
    now = _resolve_now()
    return ToolRunResult(
        success=True,
        data={
            "matched": len(chunks) > 0,
            "chunks": [chunk.model_dump() for chunk in chunks],
        },
        error=None,
        source=SOURCE_NAME,
        retrieved_at=now,
    )


def retrieve_animal_info(query: str, collection: str = "animal_cards") -> ToolRunResult:
    """retrieve_chunks -> RAG_MIN_SCORE로 필터링 -> ToolRunResult 봉투.

    검색 저장소 자체 오류만 success=false로 구분한다 (결과 없음과 다름).
    """
    now = _resolve_now()
    _, min_score = _resolve_thresholds()

    try:
        chunks = retrieve_chunks(query, collection=collection)
    except Exception:  # 저장소 접근 장애 (A-14)
        # ToolError 계약: 내부 예외 원문·경로·키를 그대로 노출하지 않는다.
        # 실제 예외 내용은 서버 로그 등 별도 채널로만 남긴다(이 계층 밖 책임).
        return ToolRunResult(
            success=False,
            data={},
            error=ToolError(
                code="RAG_SEARCH_ERROR",
                message="동물 정보 검색 중 오류가 발생했습니다.",
            ),
            source=SOURCE_NAME,
            retrieved_at=now,
        )

    qualified = [chunk for chunk in chunks if chunk.score >= min_score]
    return answer_with_citations(query, qualified)
