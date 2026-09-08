"""공공 날씨 정보를 MCP에 노출하는 교육용 Mock Tool."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from backend.app.core.config import try_get_settings
from backend.app.schemas.tools import PublicWeatherInput, ToolError, ToolRunResult


SOURCE_NAME = "mock_public_weather"
_SEOUL = ZoneInfo("Asia/Seoul")

# 실제 공공데이터 API 연동 전까지 사용하는 결정적인 교육용 응답이다.
# 운영 JSON(data/operations/weather.json)은 다른 담당자 소유이므로 이 모듈에서 만들지 않는다.
_MOCK_CONDITIONS = {
    "서울": "맑음",
    "서울특별시": "맑음",
    "광진구": "구름많음",
    "서울어린이대공원": "구름많음",
}


def _resolve_now() -> datetime:
    settings = try_get_settings()
    if settings is not None:
        demo_now = settings.demo_now_datetime()
        if demo_now is not None:
            return demo_now
    return datetime.now(_SEOUL)


def lookup_public_weather(region: str) -> dict[str, Any]:
    """지역의 현재 날씨를 교육용 Mock 데이터에서 조회한다.

    실제 KMA 연동 전 단계이므로 지원하지 않는 지역은 임의 날씨를 생성하지 않고
    명시적인 ``REGION_NOT_FOUND`` 오류로 반환한다.
    """
    now = _resolve_now()

    try:
        validated = PublicWeatherInput.model_validate({"region": region}, strict=True)
    except ValidationError:
        return ToolRunResult(
            success=False,
            data={},
            error=ToolError(
                code="INVALID_ARGUMENT",
                message="날씨를 조회할 지역 이름을 확인해 주세요.",
            ),
            source=SOURCE_NAME,
            retrieved_at=now,
        ).model_dump(mode="json")

    condition = _MOCK_CONDITIONS.get(validated.region)
    if condition is None:
        return ToolRunResult(
            success=False,
            data={},
            error=ToolError(
                code="REGION_NOT_FOUND",
                message=f"'{validated.region}'의 교육용 날씨 정보를 찾을 수 없습니다.",
            ),
            source=SOURCE_NAME,
            retrieved_at=now,
        ).model_dump(mode="json")

    return ToolRunResult(
        success=True,
        data={
            "region": validated.region,
            "condition": condition,
            "as_of": now.isoformat(),
        },
        error=None,
        source=SOURCE_NAME,
        retrieved_at=now,
    ).model_dump(mode="json")
