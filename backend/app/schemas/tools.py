"""RAG와 MCP Tool의 입력·출력·오류 계약을 정의한다."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator


RiskLevel = Literal["read", "change", "forbidden"]


class ToolError(BaseModel):
    """Tool 실행 실패 시 사용자에게 안전하게 전달할 오류 정보다."""

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
    """Runtime이 실제로 시도한 Tool 호출과 결과를 저장한다."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)
    risk: RiskLevel
    result: ToolRunResult


class FeedingScheduleInput(BaseModel):
    """먹이시간 Tool이 허용하는 엄격한 입력 형식이다."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    habitat: StrictStr = Field(min_length=1, max_length=100)


class ClosureStatusInput(BaseModel):
    """휴장 상태 Tool이 허용하는 엄격한 입력 형식이다."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    habitat: StrictStr | None = Field(default=None, min_length=1, max_length=100)


class HabitatRouteInput(BaseModel):
    """경로 조회 Tool이 허용하는 엄격한 입력 형식이다."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    current: StrictStr = Field(min_length=1, max_length=100)
    destination: StrictStr = Field(min_length=1, max_length=100)


class FeedingScheduleData(BaseModel):
    """먹이시간 조회 Tool이 성공했을 때 반환하는 운영 데이터다."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    habitat: str = Field(min_length=1)
    animal: str = Field(min_length=1)
    next_feeding_at: datetime | None = None
    location: str = Field(min_length=1)
    as_of: datetime


class ClosureItem(BaseModel):
    """휴장 상태 조회 결과 안의 서식지 한 건이다."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    habitat: str = Field(min_length=1)
    closed: bool
class ClosureStatusData(BaseModel):
    """휴장 상태 조회 Tool이 성공했을 때 반환하는 운영 데이터다."""
    reason: str | None = None



    model_config = ConfigDict(extra="forbid")

    items: list[ClosureItem] = Field(default_factory=list)
    as_of: datetime


class HabitatRouteData(BaseModel):
    """경로 조회 Tool이 성공했을 때 반환하는 운영 데이터다."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    current: str = Field(min_length=1)
    destination: str = Field(min_length=1)
    path: list[str] = Field(min_length=1)
    estimated_minutes: int = Field(ge=0)
    as_of: datetime

class RouteInput(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    current: str = Field(min_length=1, max_length=100)
    destination: str = Field(min_length=1, max_length=100)
