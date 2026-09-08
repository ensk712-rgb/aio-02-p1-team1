"""Agent 예약 Tool 입력 계약을 검증하는 테스트다.

예약 API 요청 모델과 Agent 내부 Tool 모델은 역할이 다르다.
이 테스트는 Model Provider가 제안한 예약 인자를 Backend가 엄격하게
검증할 수 있는지 확인한다.
"""

import pytest
from pydantic import ValidationError

from backend.app.schemas.tools import ReservationToolInput


def test_reservation_tool_input_accepts_valid_arguments() -> None:
    """올바른 예약 Tool 인자는 검증 후 그대로 사용할 수 있어야 한다."""
    reservation = ReservationToolInput.model_validate(
        {
            "program": "사육사 체험",
            "visit_time": "2026-09-10T15:00:00+09:00",
            "headcount": 2,
        },
        strict=True,
    )

    assert reservation.program == "사육사 체험"
    assert reservation.visit_time == "2026-09-10T15:00:00+09:00"
    assert reservation.headcount == 2


@pytest.mark.parametrize(
    "arguments",
    [
        {
            "program": "사육사 체험",
            "visit_time": "2026-09-10T15:00:00+09:00",
            "headcount": "2",
        },
        {
            "program": "사육사 체험",
            "visit_time": "2026-09-10T15:00:00+09:00",
            "headcount": 0,
        },
        {
            "program": "사육사 체험",
            "visit_time": "2026-09-10T15:00:00+09:00",
            "headcount": 11,
        },
        {
            "program": "사육사 체험",
            "visit_time": "2026-09-10T15:00:00+09:00",
            "headcount": 2,
            "user_id": "클라이언트가_임의로_보낸_값",
        },
        {
            "program": "   ",
            "visit_time": "2026-09-10T15:00:00+09:00",
            "headcount": 2,
        },
        {
            "program": "사육사 체험",
            "visit_time": "   ",
            "headcount": 2,
        },
    ],
)
def test_reservation_tool_input_rejects_invalid_arguments(
    arguments: dict[str, object],
) -> None:
    """문자열 인원, 범위 밖 인원, 허용되지 않은 추가 필드는 거절해야 한다."""
    with pytest.raises(ValidationError):
        ReservationToolInput.model_validate(arguments, strict=True)