"""운영 조회 Tool (최두나 소유, 작업지시서 v1.1 4.1/4.2/11.4절).

이 모듈은 순수 Python 조회 함수만 담는다. FastAPI 앱, Agent Runtime, MCP Client를
import하지 않는다 — mcp_server 프로세스가 이 모듈을 그대로 재사용(코드 재사용)하기
때문에, 여기서 FastAPI/Runtime을 import하면 순환 의존이 생긴다.

위험도: 전부 read. P0 3종(get_feeding_schedule/check_closure_status/
find_habitat_route) + P1 lookup_ticket_scope.
"""

from __future__ import annotations

import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from backend.app.core.config import DATA_DIR, try_get_settings
from backend.app.schemas.common import ToolError, ToolRunResult
from backend.app.schemas.tools import (
    ClosureStatusInput,
    FeedingScheduleInput,
    RouteInput,
    TicketScopeInput,
)

SOURCE_NAME = "mock_zoo_operations"
_SEOUL = ZoneInfo("Asia/Seoul")


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
