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


def test_course_info_input_accepts_list_and_named_course_requests() -> None:
    """코스 이름이 없으면 전체 목록, 이름이 있으면 해당 코스를 조회할 수 있어야 한다."""
    all_courses = CourseInfoInput.model_validate({}, strict=True)
    named_course = CourseInfoInput.model_validate(
        {"name": "  아이동반 코스  "},
        strict=True,
    )

    assert all_courses.name is None
    assert named_course.name == "아이동반 코스"


@pytest.mark.parametrize(
    "arguments",
    [
        {"name": ""},
        {"name": "   "},
        {"name": 123},
        {"name": "아이동반 코스", "available_minutes": 60},
    ],
)
def test_course_info_input_rejects_invalid_arguments(
    arguments: dict[str, object],
) -> None:
    """빈 이름, 숫자 이름, 계약에 없는 추가 인자는 Tool 실행 전에 거절해야 한다."""
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