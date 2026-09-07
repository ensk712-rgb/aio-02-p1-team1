"""공통 API와 Tool 데이터 계약이 깨지지 않는지 확인하는 테스트다."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from backend.app.schemas.agent import AgentAskRequest
from backend.app.schemas.rag import RagInput
from backend.app.schemas.tools import ToolRunResult


def test_agent_ask_request_accepts_valid_input() -> None:
    """정상적인 관람객 질문은 요청 모델을 통과해야 한다."""
    request = AgentAskRequest(
        message="지금 펭귄 먹이시간이야?",
        session_id=None,
    )

    assert request.message == "지금 펭귄 먹이시간이야?"
    assert request.session_id is None


def test_agent_ask_request_rejects_unknown_field() -> None:
    """프론트엔드가 Tool 이름을 직접 보내는 우회 입력을 거절해야 한다."""
    with pytest.raises(ValidationError):
        AgentAskRequest(
            message="펭귄 먹이시간 알려줘",
            session_id=None,
            tool_name="delete_database",
        )


def test_rag_input_allows_only_animal_cards() -> None:
    """P0에서는 animal_cards 컬렉션만 검색할 수 있어야 한다."""
    with pytest.raises(ValidationError):
        RagInput(query="호랑이", collection="private_documents")


def test_tool_result_requires_timezone() -> None:
    """Tool 조회 시각에 시간대가 없으면 운영 시간 혼동을 막기 위해 거절한다."""
    with pytest.raises(ValidationError):
        ToolRunResult(
            success=True,
            data={},
            error=None,
            source="mock_zoo_operations",
            retrieved_at=datetime(2026, 9, 6, 13, 0),
        )


def test_tool_result_accepts_timezone_aware_datetime() -> None:
    """시간대가 포함된 Tool 결과는 정상적으로 생성되어야 한다."""
    result = ToolRunResult(
        success=True,
        data={"habitat": "해양관"},
        error=None,
        source="mock_zoo_operations",
        retrieved_at=datetime(2026, 9, 6, 13, 0, tzinfo=timezone.utc),
    )

    assert result.success is True
