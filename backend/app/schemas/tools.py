"""RAG와 운영 Tool의 입력·출력·오류 계약을 정의한다."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr

from backend.app.schemas.common import ToolError, ToolRunResult  # noqa: F401 (재노출)

RiskLevel = Literal["read", "change", "forbidden"]


class ToolCallRecord(BaseModel):
    """Runtime이 실제로 시도한 Tool 호출과 결과를 기록한다."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)
    risk: RiskLevel
    result: ToolRunResult


class FeedingScheduleInput(BaseModel):
    """먹이시간 조회 Tool의 엄격한 입력 형식이다."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    habitat: StrictStr = Field(min_length=1, max_length=100)


class ClosureStatusInput(BaseModel):
    """휴장 상태 조회 Tool의 엄격한 입력 형식이다."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    habitat: StrictStr | None = Field(default=None, min_length=1, max_length=100)


class HabitatRouteInput(BaseModel):
    """Agent Runtime 경로 조회 Tool의 엄격한 입력 형식이다."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    current: StrictStr = Field(min_length=1, max_length=100)
    destination: StrictStr = Field(min_length=1, max_length=100)


class RouteInput(BaseModel):
    """운영 조회 함수가 사용하는 경로 조회 입력 형식이다.

    기존 ``zoo_tools.py``가 이 이름을 사용하므로 이름을 유지한다.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    current: str = Field(min_length=1, max_length=100)
    destination: str = Field(min_length=1, max_length=100)


class FeedingScheduleData(BaseModel):
    """먹이시간 조회 성공 시 반환하는 운영 데이터다."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    habitat: str = Field(min_length=1)
    animal: str = Field(min_length=1)
    next_feeding_at: datetime | None = None
    location: str = Field(min_length=1)
    as_of: datetime


class ClosureItem(BaseModel):
    """휴장 상태 조회 결과의 시설 한 건이다."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    habitat: str = Field(min_length=1)
    closed: bool


class ClosureStatusData(BaseModel):
    """휴장 상태 조회 Tool이 성공했을 때 반환하는 운영 데이터다."""

    model_config = ConfigDict(extra="forbid")

    # 기존 공통 계약의 필드 위치를 유지한다.
    reason: str | None = None
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


class ChunkInput(BaseModel):
    """document_repository.insert_chunks에 전달하는 청크 한 건이다."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    doc_id: str = Field(min_length=1)
    collection: str = Field(min_length=1)
    title: str = Field(min_length=1)
    page: int | None = Field(default=None, ge=1)
    text: str = Field(min_length=1)
    keywords: list[str] = Field(default_factory=list)


class ReservationToolInput(BaseModel):
    """Agent가 제안한 예약 Tool 인자를 엄격하게 검증한다.

    이 모델은 화면 예약 API 요청용이 아니라, Model Provider가 Agent Runtime에
    제안한 Tool 인자를 검증한다.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    program: StrictStr = Field(
        min_length=1,
        max_length=100,
        description="예약할 체험 프로그램 이름",
    )
    visit_time: StrictStr = Field(
        min_length=1,
        max_length=50,
        description="시간대를 포함한 예약 희망 시각 문자열",
    )
    headcount: StrictInt = Field(
        ge=1,
        le=10,
        description="예약 인원 수. 1명 이상 10명 이하여야 한다.",
    )


class TicketScopeInput(BaseModel):
    """Agent가 티켓 이용 범위 조회 Tool에 전달하는 입력 계약이다.

    실제 티켓 조회 함수는 최두나 담당이다.
    이 모델은 함수가 병합되기 전에 Agent 입력 형식을 먼저 고정한다.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    ticket_type: StrictStr = Field(
        min_length=1,
        max_length=100,
        description="조회할 티켓 종류 이름",
    )


class CourseInfoInput(BaseModel):
    """맞춤 코스 추천 Tool(get_course_info/get_indoor_course_info/
    get_outdoor_course_info)의 엄격한 입력 형식이다. 세 Tool이 이 계약을
    동일하게 공유한다(P1-B 맞춤 코스 추천 계획서 §5.1).
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    available_minutes: StrictInt = Field(ge=1, le=600)
    child_accompanying: bool = False
    current: StrictStr = Field(default="정문", min_length=1, max_length=100)


class PublicWeatherInput(BaseModel):
    """Agent가 날씨 조회 Tool에 전달하는 입력 계약이다.

    실제 날씨 MCP Tool은 이원민 담당이다.
    이 모델은 MCP Tool이 병합되기 전에 Agent 입력 형식을 먼저 고정한다.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    region: StrictStr = Field(
        min_length=1,
        max_length=100,
        description="날씨를 조회할 지역 이름",
    )


class PublicWeatherData(BaseModel):
    """날씨 조회 Tool(lookup_public_weather)이 성공했을 때 반환하는 데이터다.

    실제 값은 Open-Meteo API의 WMO weather code를 condition 4종으로 매핑한
    결과다(P1-B 맞춤 코스 추천 계획서 §5.2.1).
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    region: str = Field(min_length=1)
    condition: Literal["clear", "cloudy", "rain", "storm"]
    indoor_recommended: bool
    as_of: datetime
