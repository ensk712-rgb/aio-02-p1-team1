"""맞춤 코스 추천 Tool 선택을 위한 날씨 선조회 + 동적 Allowlist 좁히기.

P1-B 맞춤 코스 추천 계획서 §6.2(4차 회의 확정) 구현이다.

Runtime이 zoo_guide 요청을 처리하기 전에 날씨를 선조회해서, 그 결과에 따라
`get_course_info`(실내+실외 겸용)와 `get_indoor_course_info`(실내 전용) 중
하나만 이번 요청의 유효 Allowlist에 남긴다. LLM은 narrowing된 Tool 목록만
보게 되므로, "날씨를 알고도 잘못된 Tool을 부르는" 경우 자체가 구조적으로
불가능해진다 — v1.2가 Agent Instructions만으로 이 선택을 유도했다가 겪었던
신뢰성 문제를 Runtime의 Allowlist 통제로 해소한다.

`get_outdoor_course_info`는 날씨와 무관하게 항상 유효 Allowlist에 남는다
(계획서 §5.0) — 사용자가 실외 코스를 명시적으로 요청할 때 쓰는 별도 Tool이라
이 narrowing의 대상이 아니다.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime

from backend.app.agents.models import AgentProfile
from backend.app.schemas.tools import ToolRunResult
from backend.app.tools.zoo_tools import (
    get_course_info,
    get_indoor_course_info,
    lookup_public_weather,
)

# region은 course의 current(시설명)가 아니라 동물원을 대표하는 고정 지역명이다
# — 동물원이 서울 소재라 서울만 조회하면 충분하다(계획서 §5.2.1, §6.2).
WEATHER_REGION = "서울"

_ALL_WEATHER_COURSE_TOOL = "get_course_info"
_INDOOR_ONLY_COURSE_TOOL = "get_indoor_course_info"


@dataclass(frozen=True)
class WeatherNarrowingResult:
    """narrow_course_tools_by_weather() 한 번 실행 결과다.

    profile: (좁혀졌을 수도 있는) 이번 요청에 쓸 Profile.
    applied: 실제로 narrowing이 일어났는지(두 Tool이 모두 있었는지) 여부.
    weather: 선조회한 lookup_public_weather() 원본 결과(applied=False면 None).
             §7 화면 표시가 "날씨 선조회 실패"를 판단할 때 이 값을 Trace로
             기록해 참조한다.
    """

    profile: AgentProfile
    applied: bool
    weather: ToolRunResult | None


async def _resolve_indoor_recommended(
    *, now: datetime | None = None
) -> tuple[bool, ToolRunResult]:
    """날씨를 선조회해 (실내를 권장하는지, 원본 lookup_public_weather 결과)를 반환한다.

    narrow_course_tools_by_weather()(§6.2, Agent Runtime narrowing)와
    recommend_course_with_weather()(§11.4, REST 엔드포인트)가 이 함수 하나를
    공유한다 — "날씨 선조회 + Tool 선택" 로직을 두 곳에 따로 구현하지 않는다
    (계획서 §11.4 "재사용해야 한다" 요구사항).

    lookup_public_weather는 동기 함수이고 캐시 미스 시 실제 네트워크 호출이
    있어(약 1~2초) 이벤트 루프를 블로킹할 수 있으므로 별도 스레드에서 돌린다.
    """
    weather = await asyncio.to_thread(lookup_public_weather, WEATHER_REGION, now=now)
    indoor_recommended = bool(weather.success and weather.data.get("indoor_recommended"))
    return indoor_recommended, weather


async def narrow_course_tools_by_weather(
    profile: AgentProfile, *, now: datetime | None = None
) -> WeatherNarrowingResult:
    """요청마다 get_course_info/get_indoor_course_info 중 하나만 남긴 새 Profile을 만든다.

    두 Tool이 모두 allowed_tools에 있는 Profile에만 의미가 있다 — 하나라도
    없으면(다른 Agent이거나 아직 등록 전이면) 원본을 그대로 돌려준다.

    날씨 선조회가 성공하고 비/악천후(indoor_recommended=true)면
    get_course_info를 빼고 get_indoor_course_info만 남긴다. 그 외 모든
    경우(맑음/흐림이거나 조회 실패)에는 get_indoor_course_info를 빼고
    get_course_info만 남긴다 — 날씨를 모른다고 실내로 좁혀서 실외 코스를
    놓치게 하지 않는다(계획서 §5.2.1·§6.2 "안전한 기본 동작").
    """
    tool_names = {policy.name for policy in profile.allowed_tools}
    if not {_ALL_WEATHER_COURSE_TOOL, _INDOOR_ONLY_COURSE_TOOL} <= tool_names:
        return WeatherNarrowingResult(profile=profile, applied=False, weather=None)

    indoor_recommended, weather = await _resolve_indoor_recommended(now=now)

    excluded_tool = (
        _ALL_WEATHER_COURSE_TOOL if indoor_recommended else _INDOOR_ONLY_COURSE_TOOL
    )

    narrowed_tools = tuple(
        policy for policy in profile.allowed_tools if policy.name != excluded_tool
    )
    narrowed_profile = profile.model_copy(update={"allowed_tools": narrowed_tools})
    return WeatherNarrowingResult(profile=narrowed_profile, applied=True, weather=weather)


async def recommend_course_with_weather(
    *,
    available_minutes: int,
    child_accompanying: bool = False,
    current: str = "정문",
    now: datetime | None = None,
) -> ToolRunResult:
    """§6.2와 같은 날씨 판단으로 get_course_info 또는 get_indoor_course_info
    중 하나를 호출해 코스를 계산한다.

    Agent Runtime을 거치지 않는 GET /api/tools/course-info(§11.4)가 이
    함수를 쓴다 — narrow_course_tools_by_weather()와 판단 로직
    (_resolve_indoor_recommended)을 공유하므로, 지도 화면과 채팅 화면이
    같은 조건에서 서로 다른 코스를 보여주는 일이 없다.

    반환하는 data에 weather_lookup_succeeded를 함께 담는다 — scope를
    생략해 날씨로 자동 선택한 경우, 화면(§7)이 "날씨가 맑아서
    get_course_info가 선택됨"과 "날씨 조회 자체가 실패해 기본값으로
    get_course_info가 선택됨"을 구분할 방법이 이것 말고는 없다(둘 다
    facility_scope="all"로 동일하게 보이기 때문).
    """
    indoor_recommended, weather = await _resolve_indoor_recommended(now=now)
    if indoor_recommended:
        result = get_indoor_course_info(available_minutes, child_accompanying, current, now=now)
    else:
        result = get_course_info(available_minutes, child_accompanying, current, now=now)
    return result.model_copy(
        update={"data": {**result.data, "weather_lookup_succeeded": weather.success}}
    )
