"""운영 조회 Tool (최두나 소유, 작업지시서 v1.1 4.1/4.2/11.4절).

이 모듈은 순수 Python 조회 함수만 담는다. FastAPI 앱, Agent Runtime, MCP Client를
import하지 않는다 — mcp_server 프로세스가 이 모듈을 그대로 재사용(코드 재사용)하기
때문에, 여기서 FastAPI/Runtime을 import하면 순환 의존이 생긴다.

위험도: 전부 read. P0 3종(get_feeding_schedule/check_closure_status/
find_habitat_route) + P1 lookup_ticket_scope + P1-B 맞춤 코스 추천
(lookup_public_weather, get_course_info/get_indoor_course_info/
get_outdoor_course_info).
"""

from __future__ import annotations

import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

import httpx
from pydantic import ValidationError

from backend.app.core.config import DATA_DIR, try_get_settings
from backend.app.schemas.common import ToolError, ToolRunResult
from backend.app.schemas.tools import (
    ClosureStatusInput,
    CourseInfoInput,
    FeedingScheduleInput,
    PublicWeatherInput,
    RouteInput,
    TicketScopeInput,
)

FacilityScope = Literal["all", "indoor_only", "outdoor_only"]

SOURCE_NAME = "mock_zoo_operations"
_SEOUL = ZoneInfo("Asia/Seoul")

# P1-B 맞춤 코스 추천: 날씨 Tool (Open-Meteo). 이번 범위는 "서울"만 지원한다 —
# 동물원이 서울 소재이므로 서울 지역만 조회하면 충분하다(P1-B 계획서 §5.2.1).
OPEN_METEO_SOURCE = "open_meteo_forecast"
_OPEN_METEO_BASE_URL = "https://api.open-meteo.com/v1/forecast"
_OPEN_METEO_TIMEOUT_SECONDS = 5.0
_REGION_COORDINATES: dict[str, tuple[float, float]] = {
    "서울": (37.5665, 126.9780),
}

# TTL 10분 캐싱, 수동 무효화 없음(P1-B 계획서 §5.2.1·§6.2 4차 회의 확정). Runtime의
# 날씨 선조회든 Agent의 직접 호출이든 이 Tool 함수를 그냥 호출하기만 하면 캐시가
# 투명하게 적용된다 — 호출자가 캐시를 따로 관리하지 않는다.
_WEATHER_CACHE_TTL_SECONDS = 600
_weather_cache: dict[str, tuple[datetime, dict[str, Any]]] = {}


def _reset_weather_cache_for_tests() -> None:
    """테스트에서 캐시 상태를 초기화할 때만 사용한다(운영 코드에서는 호출하지 않는다)."""
    _weather_cache.clear()


def _load_json(relative_path: str) -> dict[str, Any]:
    path: Path = DATA_DIR / relative_path
    with path.open(encoding="utf-8") as f:
        return json.load(f)


@lru_cache
def _habitat_alias_map() -> dict[str, str]:
    """별칭(공백 제거·소문자) -> 정규 시설명."""
    payload = _load_json("operations/habitats.json")
    mapping: dict[str, str] = {}
    for habitat in payload["habitats"]:
        canonical = habitat["name"]
        for alias in habitat["aliases"]:
            mapping[_normalize_alias(alias)] = canonical
    return mapping


def _normalize_alias(value: str) -> str:
    return value.strip().lower()


def normalize_habitat(raw: str) -> str | None:
    """별칭을 포함해 정규 시설명으로 변환한다. 등록되지 않은 시설은 None."""
    return _habitat_alias_map().get(_normalize_alias(raw))


@lru_cache
def _ticket_alias_map() -> dict[str, str]:
    """별칭(공백 제거·소문자) -> 정규 티켓 종류명."""
    payload = _load_json("operations/tickets.json")
    mapping: dict[str, str] = {}
    for ticket in payload["tickets"]:
        canonical = ticket["ticket_type"]
        for alias in ticket["aliases"]:
            mapping[_normalize_alias(alias)] = canonical
    return mapping


def normalize_ticket_type(raw: str) -> str | None:
    """별칭을 포함해 정규 티켓 종류명으로 변환한다. 등록되지 않은 종류는 None."""
    return _ticket_alias_map().get(_normalize_alias(raw))


@lru_cache
def _course_profile_map() -> dict[str, dict[str, Any]]:
    """정규 시설명 -> {visit_minutes, child_friendly, indoor}."""
    payload = _load_json("operations/course_profiles.json")
    return {row["habitat"]: row for row in payload["profiles"]}


def get_course_profile(habitat: str) -> dict[str, Any] | None:
    """정규화된 시설명으로 코스 프로필 한 건을 조회한다. 없으면 None."""
    canonical = normalize_habitat(habitat)
    if canonical is None:
        return None
    return _course_profile_map().get(canonical)


def _resolve_now() -> datetime:
    settings = try_get_settings()
    if settings is not None:
        demo_now = settings.demo_now_datetime()
        if demo_now is not None:
            return demo_now
    return datetime.now(_SEOUL)


def _not_found_result(code: str, message: str) -> ToolRunResult:
    return ToolRunResult(
        success=False,
        data={},
        error=ToolError(code=code, message=message),
        source=SOURCE_NAME,
        retrieved_at=_resolve_now(),
    )


def get_feeding_schedule(habitat: str, *, now: datetime | None = None) -> ToolRunResult:
    """habitat의 다음 먹이시간을 조회한다.

    같은 시설에 동물이 여러 종이면(예: 해양관=펭귄+물개) 그중 가장 가까운
    다음 먹이시간을 대표로 반환한다. 오늘 남은 일정이 없으면 그 시설의 첫
    번째 항목을 기준으로 next_feeding_at=null을 반환한다.

    now: 테스트/평가에서 결정적 시각을 주입할 때 사용한다. 생략하면
    DEMO_NOW(.env) 또는 실제 Asia/Seoul 현재 시각을 쓴다.
    """
    try:
        validated = FeedingScheduleInput(habitat=habitat)
    except ValidationError as exc:
        return _not_found_result("INVALID_ARGUMENT", str(exc))

    canonical = normalize_habitat(validated.habitat)
    if canonical is None:
        return _not_found_result(
            "HABITAT_NOT_FOUND", f"'{habitat}'은(는) 등록된 시설이 아닙니다."
        )

    now = now or _resolve_now()
    payload = _load_json("operations/feeding.json")
    rows = [row for row in payload["schedules"] if row["habitat"] == canonical]

    if not rows:
        return ToolRunResult(
            success=True,
            data={
                "habitat": canonical,
                "animal": None,
                "next_feeding_at": None,
                "location": None,
                "as_of": now.isoformat(),
            },
            error=None,
            source=SOURCE_NAME,
            retrieved_at=now,
        )

    best_animal = None
    best_location = None
    best_next: datetime | None = None
    for row in rows:
        next_dt = _next_time_today(row["times"], now)
        if best_animal is None:
            best_animal, best_location = row["animal"], row["location"]
        if next_dt is not None and (best_next is None or next_dt < best_next):
            best_next = next_dt
            best_animal, best_location = row["animal"], row["location"]

    return ToolRunResult(
        success=True,
        data={
            "habitat": canonical,
            "animal": best_animal,
            "next_feeding_at": best_next.isoformat() if best_next else None,
            "location": best_location,
            "as_of": now.isoformat(),
        },
        error=None,
        source=SOURCE_NAME,
        retrieved_at=now,
    )


def _next_time_today(times: list[str], now: datetime) -> datetime | None:
    candidates = []
    for hhmm in times:
        hour, minute = (int(part) for part in hhmm.split(":"))
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate > now:
            candidates.append(candidate)
    return min(candidates) if candidates else None


def check_closure_status(
    habitat: str | None = None, *, now: datetime | None = None
) -> ToolRunResult:
    """habitat=None이면 전체 시설 상태를, 지정하면 해당 시설 하나를 items 목록으로 반환."""
    try:
        validated = ClosureStatusInput(habitat=habitat)
    except ValidationError as exc:
        return _not_found_result("INVALID_ARGUMENT", str(exc))

    now = now or _resolve_now()
    payload = _load_json("operations/closures.json")
    all_rows = payload["closures"]

    if validated.habitat is None:
        items = [
            {"habitat": row["habitat"], "closed": row["closed"], "reason": row["reason"]}
            for row in all_rows
        ]
        return ToolRunResult(
            success=True,
            data={"items": items, "as_of": now.isoformat()},
            error=None,
            source=SOURCE_NAME,
            retrieved_at=now,
        )

    canonical = normalize_habitat(validated.habitat)
    if canonical is None:
        return _not_found_result(
            "HABITAT_NOT_FOUND", f"'{habitat}'은(는) 등록된 시설이 아닙니다."
        )

    row = next((r for r in all_rows if r["habitat"] == canonical), None)
    if row is None:
        return _not_found_result(
            "HABITAT_NOT_FOUND", f"'{habitat}'의 휴장 정보를 찾을 수 없습니다."
        )

    items = [{"habitat": row["habitat"], "closed": row["closed"], "reason": row["reason"]}]
    return ToolRunResult(
        success=True,
        data={"items": items, "as_of": now.isoformat()},
        error=None,
        source=SOURCE_NAME,
        retrieved_at=now,
    )


def find_habitat_route(
    current: str, destination: str, *, now: datetime | None = None
) -> ToolRunResult:
    try:
        validated = RouteInput(current=current, destination=destination)
    except ValidationError as exc:
        return _not_found_result("INVALID_ARGUMENT", str(exc))

    now = now or _resolve_now()
    canonical_current = normalize_habitat(validated.current)
    canonical_destination = normalize_habitat(validated.destination)

    if canonical_current is None or canonical_destination is None:
        bad = current if canonical_current is None else destination
        return _not_found_result(
            "HABITAT_NOT_FOUND", f"'{bad}'은(는) 등록된 시설이 아닙니다."
        )

    if canonical_current == canonical_destination:
        return ToolRunResult(
            success=True,
            data={
                "current": canonical_current,
                "destination": canonical_destination,
                "path": [canonical_current],
                "estimated_minutes": 0,
                "as_of": now.isoformat(),
            },
            error=None,
            source=SOURCE_NAME,
            retrieved_at=now,
        )

    payload = _load_json("operations/routes.json")
    row = next(
        (
            r
            for r in payload["routes"]
            if r["current"] == canonical_current and r["destination"] == canonical_destination
        ),
        None,
    )
    if row is None:
        return _not_found_result(
            "ROUTE_NOT_FOUND",
            f"'{canonical_current}'에서 '{canonical_destination}'까지의 경로를 찾을 수 없습니다.",
        )

    return ToolRunResult(
        success=True,
        data={
            "current": canonical_current,
            "destination": canonical_destination,
            "path": row["path"],
            "estimated_minutes": row["estimated_minutes"],
            "as_of": now.isoformat(),
        },
        error=None,
        source=SOURCE_NAME,
        retrieved_at=now,
    )


def lookup_ticket_scope(ticket_type: str, *, now: datetime | None = None) -> ToolRunResult:
    """ticket_type으로 관람 가능한 전시관(included)과 제외 항목(excluded)을 조회한다.

    작업지시서 v1.1 11.4절 계약: data={ticket_type, included, excluded}.
    시간 기준 데이터가 아니므로 as_of는 포함하지 않는다(다른 3종 Tool과 차이).
    """
    try:
        validated = TicketScopeInput(ticket_type=ticket_type)
    except ValidationError as exc:
        return _not_found_result("INVALID_ARGUMENT", str(exc))

    now = now or _resolve_now()
    canonical = normalize_ticket_type(validated.ticket_type)
    if canonical is None:
        return _not_found_result(
            "TICKET_TYPE_NOT_FOUND", f"'{ticket_type}'은(는) 등록된 티켓 종류가 아닙니다."
        )

    payload = _load_json("operations/tickets.json")
    row = next(r for r in payload["tickets"] if r["ticket_type"] == canonical)

    return ToolRunResult(
        success=True,
        data={
            "ticket_type": row["ticket_type"],
            "included": row["included"],
            "excluded": row["excluded"],
        },
        error=None,
        source=SOURCE_NAME,
        retrieved_at=now,
    )


def _map_weather_code(code: int) -> str:
    """Open-Meteo의 WMO weather code(0~99)를 condition 4종으로 매핑한다.

    P1-B 계획서 §5.2.1의 제안 매핑표를 그대로 따른다:
    0=clear / 1,2,3,45,48=cloudy / 95,96,99=storm / 그 외 강수 코드=rain.
    """
    if code == 0:
        return "clear"
    if code in {1, 2, 3, 45, 48}:
        return "cloudy"
    if code in {95, 96, 99}:
        return "storm"
    return "rain"


def _weather_error_result(code: str, message: str, *, now: datetime | None = None) -> ToolRunResult:
    """lookup_public_weather 전용 오류 결과.

    공용 _not_found_result()는 source를 항상 SOURCE_NAME("mock_zoo_operations")
    으로 고정하는데, 이 Tool은 성공이든 실패든 Mock 데이터를 다루지 않고 항상
    Open-Meteo를 대상으로 하므로 실패 시에도 OPEN_METEO_SOURCE를 써야 한다
    (P1-B 계획서 §5.2.1 — "mock"이라고 잘못 표시하지 않는다).
    """
    return ToolRunResult(
        success=False,
        data={},
        error=ToolError(code=code, message=message),
        source=OPEN_METEO_SOURCE,
        retrieved_at=now or _resolve_now(),
    )


def lookup_public_weather(region: str, *, now: datetime | None = None) -> ToolRunResult:
    """region의 현재 날씨를 Open-Meteo API로 조회해 condition 4종으로 반환한다.

    이번 범위에서는 "서울"만 지원한다(동물원이 서울 소재이므로 서울 지역만
    조회하면 충분하다, P1-B 계획서 §5.2.1). 다른 조회 Tool과 달리 Mock
    데이터가 아니라 실제 외부 API를 호출하므로 source가 SOURCE_NAME이 아니라
    OPEN_METEO_SOURCE다(성공·실패 모두).

    성공한 조회 결과는 region별로 10분(TTL, 수동 무효화 없음) 동안 캐시해
    재사용한다. 캐시된 결과의 as_of는 실제로 API를 호출했던 시각을 그대로
    유지한다(재사용 시점이 아니라 데이터의 실제 신선도를 보여줘야 하므로) —
    다만 ToolRunResult.retrieved_at은 이번 호출 시각을 쓴다.
    """
    try:
        validated = PublicWeatherInput(region=region)
    except ValidationError as exc:
        return _weather_error_result("INVALID_ARGUMENT", str(exc), now=now)

    coordinates = _REGION_COORDINATES.get(validated.region)
    if coordinates is None:
        return _weather_error_result(
            "REGION_NOT_SUPPORTED", f"'{region}'은(는) 지원하는 지역이 아닙니다.", now=now
        )

    now = now or _resolve_now()

    cached = _weather_cache.get(validated.region)
    if cached is not None:
        cached_at, cached_data = cached
        if (now - cached_at).total_seconds() < _WEATHER_CACHE_TTL_SECONDS:
            return ToolRunResult(
                success=True,
                data=cached_data,
                error=None,
                source=OPEN_METEO_SOURCE,
                retrieved_at=now,
            )

    latitude, longitude = coordinates

    settings = try_get_settings()
    api_key = settings.OPEN_METEO_API_KEY if settings is not None else ""
    params: dict[str, Any] = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "forecast_days": 5,
        "timezone": "Asia/Seoul",
    }
    if api_key:
        # 비상업용 무료 엔드포인트는 키가 필요 없다. 팀이 유료/커머셜 티어로
        # 옮기면 이 키가 자동으로 요청에 실린다(P1-B 계획서 §5.2.1).
        params["apikey"] = api_key

    try:
        response = httpx.get(
            _OPEN_METEO_BASE_URL, params=params, timeout=_OPEN_METEO_TIMEOUT_SECONDS
        )
        response.raise_for_status()
        payload = response.json()
        current = payload["current"]
        weather_code = int(current["weather_code"])
    except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
        return _weather_error_result(
            "WEATHER_LOOKUP_FAILED", f"날씨 조회에 실패했습니다: {exc}", now=now
        )

    condition = _map_weather_code(weather_code)
    data = {
        "region": validated.region,
        "condition": condition,
        "indoor_recommended": condition in {"rain", "storm"},
        "current": {
            "temperature_c": current.get("temperature_2m"),
            "apparent_temperature_c": current.get("apparent_temperature"),
            "humidity_percent": current.get("relative_humidity_2m"),
            "wind_speed_kmh": current.get("wind_speed_10m"),
            "weather_code": weather_code,
            "condition": condition,
        },
        "forecast": [],
        "as_of": now.isoformat(),
    }
    daily = payload.get("daily") or {}
    for date_value, code, high, low, rain_probability in zip(
        daily.get("time", []),
        daily.get("weather_code", []),
        daily.get("temperature_2m_max", []),
        daily.get("temperature_2m_min", []),
        daily.get("precipitation_probability_max", []),
    ):
        data["forecast"].append({
            "date": date_value,
            "weather_code": int(code),
            "condition": _map_weather_code(int(code)),
            "temperature_max_c": high,
            "temperature_min_c": low,
            "precipitation_probability_percent": rain_probability,
        })
    _weather_cache[validated.region] = (now, data)
    return ToolRunResult(
        success=True,
        data=data,
        error=None,
        source=OPEN_METEO_SOURCE,
        retrieved_at=now,
    )


def _course_candidates(facility_scope: FacilityScope) -> list[dict[str, Any]]:
    """course_profiles.json에 선언된 순서 그대로 후보를 반환한다(정렬하지 않는다).

    선언 순서 자체가 그리디 알고리즘 입력의 일부다(P1-B 계획서 §6.1) — 이
    파일을 수정하면 그리디 결과도 함께 바뀐다.
    """
    payload = _load_json("operations/course_profiles.json")
    profiles = payload["profiles"]
    if facility_scope == "indoor_only":
        return [row for row in profiles if row["indoor"]]
    if facility_scope == "outdoor_only":
        return [row for row in profiles if not row["indoor"]]
    return list(profiles)


def _closed_habitats(*, now: datetime) -> set[str]:
    result = check_closure_status(now=now)
    if not result.success:
        return set()
    return {item["habitat"] for item in result.data["items"] if item["closed"]}


def _recommend_course(
    available_minutes: int,
    child_accompanying: bool,
    current: str,
    *,
    facility_scope: FacilityScope,
    now: datetime | None = None,
) -> ToolRunResult:
    """course_profiles.json 후보를 규칙(§6)대로 그리디하게 조합해 코스를 계산한다.

    facility_scope="all"          → 전체 시설
    facility_scope="indoor_only"  → course_profiles.json의 indoor=true만
    facility_scope="outdoor_only" → course_profiles.json의 indoor=false만

    그리디 절차(§6.1):
    1. course_profiles.json 선언 순서 그대로 후보를 쓴다.
    2. child_accompanying=true면 child_friendly=true 후보를 먼저(선언 순서대로),
       그 다음 child_friendly=false 후보를 이어서(선언 순서대로) 순회한다.
    3. 각 후보를: 휴장이면 건너뛰고(규칙 2), 이미 방문했으면 건너뛰고(규칙 4),
       현재 위치에서 경로가 없으면 건너뛰고, 채택 시 누적 시간이
       available_minutes를 넘으면 건너뛴다(규칙 9) — 넘지 않으면 채택하고
       현재 위치를 갱신한다. 맞지 않는 후보에서 멈추지 않고 다음 후보를 계속
       시도한다.
    """
    try:
        validated = CourseInfoInput(
            available_minutes=available_minutes,
            child_accompanying=child_accompanying,
            current=current,
        )
    except ValidationError as exc:
        return _not_found_result("INVALID_ARGUMENT", str(exc))

    canonical_current = normalize_habitat(validated.current)
    if canonical_current is None:
        return _not_found_result(
            "HABITAT_NOT_FOUND", f"'{current}'은(는) 등록된 시설이 아닙니다."
        )

    now = now or _resolve_now()
    closed = _closed_habitats(now=now)
    candidates = _course_candidates(facility_scope)

    if validated.child_accompanying:
        ordered = [row for row in candidates if row["child_friendly"]] + [
            row for row in candidates if not row["child_friendly"]
        ]
    else:
        ordered = candidates

    stops: list[dict[str, Any]] = []
    visited: set[str] = set()
    position = canonical_current
    cumulative_minutes = 0

    for row in ordered:
        habitat = row["habitat"]
        if habitat in closed or habitat in visited:
            continue

        route_result = find_habitat_route(position, habitat, now=now)
        if not route_result.success:
            continue

        travel_minutes = route_result.data["estimated_minutes"]
        visit_minutes = row["visit_minutes"]
        candidate_total = cumulative_minutes + travel_minutes + visit_minutes
        if candidate_total > validated.available_minutes:
            continue

        stops.append(
            {
                "habitat": habitat,
                "travel_minutes": travel_minutes,
                "visit_minutes": visit_minutes,
                "cumulative_minutes": candidate_total,
            }
        )
        visited.add(habitat)
        position = habitat
        cumulative_minutes = candidate_total

    return ToolRunResult(
        success=True,
        data={
            "current": canonical_current,
            "available_minutes": validated.available_minutes,
            "facility_scope": facility_scope,
            "stops": stops,
            "total_minutes": cumulative_minutes,
            "remaining_minutes": validated.available_minutes - cumulative_minutes,
        },
        error=None,
        source=SOURCE_NAME,
        retrieved_at=now,
    )


def get_course_info(
    available_minutes: int,
    child_accompanying: bool = False,
    current: str = "정문",
    *,
    now: datetime | None = None,
) -> ToolRunResult:
    """실내+실외 모두를 후보로 코스를 추천한다(코스 추천 Tool 1/3)."""
    return _recommend_course(
        available_minutes, child_accompanying, current, facility_scope="all", now=now
    )


def get_indoor_course_info(
    available_minutes: int,
    child_accompanying: bool = False,
    current: str = "정문",
    *,
    now: datetime | None = None,
) -> ToolRunResult:
    """course_profiles.json에서 indoor=True인 시설만 후보로 사용한다(Tool 2/3)."""
    return _recommend_course(
        available_minutes,
        child_accompanying,
        current,
        facility_scope="indoor_only",
        now=now,
    )


def get_outdoor_course_info(
    available_minutes: int,
    child_accompanying: bool = False,
    current: str = "정문",
    *,
    now: datetime | None = None,
) -> ToolRunResult:
    """course_profiles.json에서 indoor=False인 시설만 후보로 사용한다(Tool 3/3)."""
    return _recommend_course(
        available_minutes,
        child_accompanying,
        current,
        facility_scope="outdoor_only",
        now=now,
    )
