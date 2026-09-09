"""P1-B 티켓·코스·날씨 조회 Tool의 입력 계약을 검증한다."""

import pytest
from pydantic import ValidationError

from backend.app.schemas.tools import (
    CourseInfoInput,
    PublicWeatherInput,
    TicketScopeInput,
)


def test_ticket_scope_input_accepts_valid_ticket_type() -> None:
    """유효한 티켓 종류는 앞뒤 공백을 제거한 뒤 사용할 수 있어야 한다."""
    ticket = TicketScopeInput.model_validate(
        {"ticket_type": "  종일권  "},
        strict=True,
    )

    assert ticket.ticket_type == "종일권"


@pytest.mark.parametrize(
    "arguments",
    [
        {"ticket_type": ""},
        {"ticket_type": "   "},
        {"ticket_type": 123},
        {"ticket_type": "종일권", "user_id": "임의값"},
    ],
)
def test_ticket_scope_input_rejects_invalid_arguments(
    arguments: dict[str, object],
) -> None:
    """빈 값, 숫자, 허용되지 않은 추가 필드는 거절해야 한다."""
    with pytest.raises(ValidationError):
        TicketScopeInput.model_validate(arguments, strict=True)


def test_course_info_input_accepts_available_minutes_with_defaults() -> None:
    """available_minutes만 있으면 child_accompanying/current는 기본값을 쓴다."""
    minimal = CourseInfoInput.model_validate(
        {"available_minutes": 120},
        strict=True,
    )
    full = CourseInfoInput.model_validate(
        {
            "available_minutes": 90,
            "child_accompanying": True,
            "current": "  해양관  ",
        },
        strict=True,
    )

    assert minimal.available_minutes == 120
    assert minimal.child_accompanying is False
    assert minimal.current == "정문"
    assert full.child_accompanying is True
    assert full.current == "해양관"


@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {"available_minutes": 0},
        {"available_minutes": 601},
        {"available_minutes": "120"},
        {"available_minutes": 120, "name": "아이동반 코스"},
    ],
)
def test_course_info_input_rejects_invalid_arguments(
    arguments: dict[str, object],
) -> None:
    """필수값 누락, 범위 밖 시간, 이전 name 인자는 거절해야 한다."""
    with pytest.raises(ValidationError):
        CourseInfoInput.model_validate(arguments, strict=True)


def test_public_weather_input_accepts_valid_region() -> None:
    """유효한 지역명은 앞뒤 공백을 제거한 뒤 사용할 수 있어야 한다."""
    weather = PublicWeatherInput.model_validate(
        {"region": "  서울  "},
        strict=True,
    )

    assert weather.region == "서울"


@pytest.mark.parametrize(
    "arguments",
    [
        {"region": ""},
        {"region": "   "},
        {"region": 123},
        {"region": "서울", "unit": "celsius"},
    ],
)
def test_public_weather_input_rejects_invalid_arguments(
    arguments: dict[str, object],
) -> None:
    """빈 값, 숫자, 허용되지 않은 추가 필드는 거절해야 한다."""
    with pytest.raises(ValidationError):
        PublicWeatherInput.model_validate(arguments, strict=True)