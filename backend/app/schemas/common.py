"""공통 모델 (작업지시서 v1.1 3.4절).

이 파일은 원래 손영민 소유(agents/API 계약)이지만, C2(RAG·운영 Tool) 구현이
이 모델들에 의존하므로 계약 표에 정의된 필드만 우선 반영해 둔다.
필드/이름을 바꿀 때는 9장 규칙대로 공통 계약 변경으로 취급한다.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Source(BaseModel):
    doc_id: str
    title: str
    page: int | None = None
    score: float = Field(ge=0, le=1)


class ToolError(BaseModel):
    """내부 예외 원문·키를 담지 않는다."""

    code: str
    message: str


class ToolRunResult(BaseModel):
    success: bool
    data: dict[str, Any] = Field(default_factory=dict)
    error: ToolError | None = None
    source: str
    retrieved_at: datetime


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


class TraceItem(BaseModel):
    owner: Literal["runtime", "ai_agent", "rag", "mcp", "policy", "human"]
    stage: str
    data: dict[str, Any] = Field(default_factory=dict)
