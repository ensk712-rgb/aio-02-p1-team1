"""동물 정보카드 검색(RAG)에 필요한 입력과 결과 모델을 정의한다."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr


class RagInput(BaseModel):
    """동물 정보카드 검색 Tool이 받는 엄격한 입력값이다."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    query: StrictStr = Field(min_length=1, max_length=500)
    collection: Literal["animal_cards"]


class RetrievedChunk(BaseModel):
    """키워드 검색에서 일치한 문서 조각 한 건이다."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    doc_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    page: int | None = Field(default=None, ge=1)
    text: str = Field(min_length=1)
    score: float = Field(ge=0, le=1)
    collection: Literal["animal_cards"]


class RagSearchData(BaseModel):
    """RAG 검색 결과를 ToolRunResult.data에 넣기 위한 데이터 구조다."""

    model_config = ConfigDict(extra="forbid")

    matched: bool
    chunks: list[RetrievedChunk] = Field(default_factory=list)