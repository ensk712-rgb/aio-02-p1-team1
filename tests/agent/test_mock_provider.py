"""ScriptedMockProvider가 Runtime 테스트에 필요한 동작을 하는지 검증한다."""

import asyncio
from datetime import datetime, timezone

import pytest

from backend.app.agents.registry import get_agent_profile
from backend.app.providers.base import ProviderToolSchema
from backend.app.providers.mock_provider import ScriptedMockProvider, is_model_provider
from backend.app.schemas.agent import ModelToolCall, ModelTurn
from backend.app.schemas.tools import ToolCallRecord, ToolRunResult


FEEDING_TOOL_SCHEMA: ProviderToolSchema = {
    "name": "get_feeding_schedule",
    "description": "특정 서식지의 다음 먹이시간을 조회한다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "habitat": {"type": "string"},
        },
        "required": ["habitat"],
        "additionalProperties": False,
    },
}


def create_feeding_result() -> ToolCallRecord:
    """두 번째 Provider 호출에 전달할 가짜 먹이시간 Tool 결과를 만든다."""
    return ToolCallRecord(
        name="get_feeding_schedule",
        arguments={"habitat": "해양관"},
        risk="read",
        result=ToolRunResult(
            success=True,
            data={
                "habitat": "해양관",
                "animal": "펭귄",
                "next_feeding_at": "2026-09-06T14:30:00+09:00",
            },
            error=None,
            source="mock_zoo_operations",
            retrieved_at=datetime(2026, 9, 6, 13, 0, tzinfo=timezone.utc),
        ),
    )


def test_mock_provider_returns_turns_in_order() -> None:
    """Provider는 Tool 호출과 최종 답변을 준비된 순서대로 반환해야 한다."""
    profile = get_agent_profile("zoo_guide")

    first_turn = ModelTurn(
        response_id="mock_response_1",
        calls=[
            ModelToolCall(
                call_id="call_1",
                name="get_feeding_schedule",
                arguments_json='{"habitat": "해양관"}',
            )
        ],
        text="",
        clarification=None,
    )
    second_turn = ModelTurn(
        response_id="mock_response_2",
        calls=[],
        text="다음 펭귄 먹이시간은 14:30입니다.",
        clarification=None,
    )
    provider = ScriptedMockProvider([first_turn, second_turn])

    returned_first_turn = asyncio.run(
        provider.next_turn(
            question="지금 펭귄 먹이시간이야?",
            instructions=profile.instructions,
            tools=[FEEDING_TOOL_SCHEMA],
            previous_response_id=None,
            tool_outputs=[],
        )
    )
    returned_second_turn = asyncio.run(
        provider.next_turn(
            question="지금 펭귄 먹이시간이야?",
            instructions=profile.instructions,
            tools=[FEEDING_TOOL_SCHEMA],
            previous_response_id="mock_response_1",
            tool_outputs=[create_feeding_result()],
        )
    )

    assert returned_first_turn.calls[0].name == "get_feeding_schedule"
    assert returned_second_turn.text == "다음 펭귄 먹이시간은 14:30입니다."
    assert provider.remaining_turns == 0


def test_mock_provider_records_tool_result_on_second_call() -> None:
    """두 번째 판단 요청에는 첫 번째 Tool 실행 결과가 전달되어야 한다."""
    profile = get_agent_profile("zoo_guide")
    provider = ScriptedMockProvider(
        [
            ModelTurn(response_id="mock_response_1"),
            ModelTurn(response_id="mock_response_2", text="조회 결과를 확인했습니다."),
        ]
    )

    asyncio.run(
        provider.next_turn(
            question="펭귄 먹이시간 알려줘",
            instructions=profile.instructions,
            tools=[FEEDING_TOOL_SCHEMA],
            previous_response_id=None,
            tool_outputs=[],
        )
    )
    asyncio.run(
        provider.next_turn(
            question="펭귄 먹이시간 알려줘",
            instructions=profile.instructions,
            tools=[FEEDING_TOOL_SCHEMA],
            previous_response_id="mock_response_1",
            tool_outputs=[create_feeding_result()],
        )
    )

    assert provider.call_history[0].tool_result_names == ()
    assert provider.call_history[1].tool_result_names == ("get_feeding_schedule",)
    assert provider.call_history[1].previous_response_id == "mock_response_1"


def test_mock_provider_rejects_empty_script() -> None:
    """반환할 응답이 없는 Provider는 생성하면 안 된다."""
    with pytest.raises(ValueError):
        ScriptedMockProvider([])


def test_mock_provider_fails_after_script_is_exhausted() -> None:
    """예정된 응답보다 많이 호출하면 테스트 시나리오 오류를 알려야 한다."""
    profile = get_agent_profile("zoo_guide")
    provider = ScriptedMockProvider([ModelTurn(response_id="mock_response_1")])

    asyncio.run(
        provider.next_turn(
            question="질문",
            instructions=profile.instructions,
            tools=[],
            previous_response_id=None,
            tool_outputs=[],
        )
    )

    with pytest.raises(RuntimeError):
        asyncio.run(
            provider.next_turn(
                question="질문",
                instructions=profile.instructions,
                tools=[],
                previous_response_id="mock_response_1",
                tool_outputs=[],
            )
        )


def test_mock_provider_matches_provider_interface() -> None:
    """Mock Provider는 Runtime이 요구하는 ModelProvider 인터페이스여야 한다."""
    provider = ScriptedMockProvider([ModelTurn(response_id="mock_response_1")])

    assert is_model_provider(provider) is True