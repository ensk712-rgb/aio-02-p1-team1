"""여러 기능에서 공통으로 사용하는 데이터 모델을 정의한다."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Source(BaseModel):
    """RAG 검색으로 답변의 근거가 된 문서 정보를 표현한다."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    doc_id: str = Field(min_length=1, description="문서를 구분하는 고유 ID")
    title: str = Field(min_length=1, description="사용자에게 보여 줄 문서 제목")
    page: int | None = Field(default=None, ge=1, description="문서 페이지 번호")
    score: float = Field(ge=0, le=1, description="검색 유사도 점수")


TraceOwner = Literal["runtime", "ai_agent", "rag", "mcp", "policy", "human"]


class TraceItem(BaseModel):
    """Agent 실행 중 발생한 사건을 기록하는 추적 로그 한 건이다."""

    model_config = ConfigDict(extra="forbid")

    owner: TraceOwner = Field(description="이 기록을 만든 시스템 영역")
    stage: str = Field(min_length=1, description="실행 단계 이름")
    data: dict[str, Any] = Field(
        default_factory=dict,
        description="단계 분석에 필요한 안전한 추가 정보",
    )