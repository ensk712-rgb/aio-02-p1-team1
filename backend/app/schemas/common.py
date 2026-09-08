"""공통 모델 (작업지시서 v1.1 3.4절).

이 파일은 원래 손영민 소유(agents/API 계약)이지만, C2(RAG·운영 Tool) 구현이
이 모델들에 의존하므로 계약 표에 정의된 필드만 우선 반영해 둔다.
필드/이름을 바꿀 때는 9장 규칙대로 공통 계약 변경으로 취급한다.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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

class ToolError(BaseModel):
    """Tool 실행 실패 시 사용자에게 안전하게 전달할 오류 정보다.

    내부 예외 원문·키를 담지 않는다.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)


class ToolRunResult(BaseModel):
    """RAG 또는 MCP Tool을 한 번 실행한 결과다."""

    model_config = ConfigDict(extra="forbid")

    success: bool
    data: dict[str, Any] = Field(default_factory=dict)
    error: ToolError | None = None
    source: str = Field(min_length=1)
    retrieved_at: datetime

    @field_validator("retrieved_at")
    @classmethod
    def validate_timezone(cls, value: datetime) -> datetime:
        """시간대 없는 조회 시각을 거절한다."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("retrieved_at에는 시간대 정보가 필요합니다.")
        return value


class ToolCallRecord(BaseModel):
    name: str
    arguments: dict[str, Any]
    risk: Literal["read", "change"]
    result: ToolRunResult


class RetrievedChunk(BaseModel):
    doc_id: str
    title: str
    page: int | None = None
    text: str
    score: float = Field(ge=0, le=1)
    collection: str


class RagInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=500)
    collection: Literal["animal_cards"]


class RagSearchData(BaseModel):
    matched: bool
    chunks: list[RetrievedChunk]
