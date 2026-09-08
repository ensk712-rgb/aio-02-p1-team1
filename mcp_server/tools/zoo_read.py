"""순수 운영 조회 함수 3종을 MCP에 노출하는 얇은 wrapper."""

from __future__ import annotations

from typing import Any

from backend.app.tools.zoo_tools import (
    check_closure_status as _check_closure_status,
    find_habitat_route as _find_habitat_route,
    get_course_info as _get_course_info,
    get_feeding_schedule as _get_feeding_schedule,
)


def get_feeding_schedule(habitat: str) -> dict[str, Any]:
    """시설의 다음 먹이시간을 교육용 운영 데이터에서 조회한다."""
    return _get_feeding_schedule(habitat).model_dump(mode="json")


def check_closure_status(habitat: str | None = None) -> dict[str, Any]:
    """전체 또는 지정 시설의 휴장 상태를 교육용 운영 데이터에서 조회한다."""
    return _check_closure_status(habitat).model_dump(mode="json")


def find_habitat_route(current: str, destination: str) -> dict[str, Any]:
    """두 시설 사이의 관람 경로를 교육용 운영 데이터에서 조회한다."""
    return _find_habitat_route(current, destination).model_dump(mode="json")


def get_course_info(name: str | None = None) -> dict[str, Any]:
    """전체 또는 지정 이름의 추천 관람 코스를 교육용 운영 데이터에서 조회한다."""
    return _get_course_info(name).model_dump(mode="json")
