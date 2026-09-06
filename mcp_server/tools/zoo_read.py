"""Backend의 순수 조회 함수를 MCP 결과 계약으로 변환하는 얇은 wrapper."""

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from backend.app.tools.zoo_tools import (
    ClosureStatusInput,
    FeedingScheduleInput,
    HabitatRouteInput,
    check_closure_status as _check_closure_status,
    find_habitat_route as _find_habitat_route,
    get_feeding_schedule as _get_feeding_schedule,
)

SEOUL = ZoneInfo("Asia/Seoul")
SOURCE = "mock_zoo_operations"


def _now_iso() -> str:
    return datetime.now(SEOUL).isoformat()


def _envelope(*, data: dict[str, Any] | None = None, code: str | None = None, message: str | None = None) -> dict[str, Any]:
    now = _now_iso()
    return {
        "success": code is None,
        "data": data or {},
        "error": None if code is None else {"code": code, "message": message or "조회에 실패했습니다."},
        "source": SOURCE,
        "retrieved_at": now,
    }


def get_feeding_schedule(habitat: str) -> dict[str, Any]:
    result = _get_feeding_schedule(FeedingScheduleInput.model_validate({"habitat": habitat}))
    if not result.get("found"):
        return _envelope(code="HABITAT_NOT_FOUND", message=result.get("message"))
    now = _now_iso()
    return _envelope(data={
        "habitat": habitat.strip(),
        "animal": result["animal"],
        "next_feeding_at": result.get("time"),
        "location": result["location"],
        "as_of": now,
    })


def check_closure_status(habitat: str | None = None) -> dict[str, Any]:
    result = _check_closure_status(ClosureStatusInput.model_validate({"habitat": habitat}))
    if habitat is None:
        items = [
            {"habitat": name, "closed": True, "reason": reason}
            for name, reason in result.get("closed_habitats", {}).items()
        ]
    else:
        items = [{"habitat": result["habitat"], "closed": result["closed"], "reason": result.get("reason")}]
    return _envelope(data={"items": items, "as_of": _now_iso()})


def find_habitat_route(current: str, destination: str) -> dict[str, Any]:
    result = _find_habitat_route(HabitatRouteInput.model_validate({"current": current, "destination": destination}))
    if not result.get("found"):
        return _envelope(code="ROUTE_NOT_FOUND", message=result.get("message"))
    return _envelope(data={
        "current": result["from"],
        "destination": result["to"],
        "path": [result["from"], result["to"]],
        "estimated_minutes": result["estimated_minutes"],
        "as_of": _now_iso(),
    })
