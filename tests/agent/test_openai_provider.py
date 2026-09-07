"""OpenAIProvider의 Responses API 변환 로직을 네트워크 없이 검증한다."""

import asyncio
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from backend.app.providers.base import ProviderToolSchema
from backend.app.providers.openai_provider import OpenAIProvider
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


class FakeResponsesApi:
    """OpenAI 네트워크 대신 준비된 응답을 순서대로 반환하는 Fake API다."""

    def __init__(self, responses: list[Any]) -> None:
        self._responses = responses
        self.requests: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        """요청 내용을 기록하고 다음 Fake 응답을 반환한다."""
        self.requests.append(kwargs)

        if not self._responses:
            raise AssertionError("준비된 Fake OpenAI 응답이 없습니다.")

        return self._responses.pop(0)


class FakeOpenAIClient:
    """OpenAIProvider가 요구하는 responses 속성만 제공하는 Fake Client다."""

    def __init__(self, responses: list[Any]) -> None:
        self.responses = FakeResponsesApi(responses)


def create_tool_result() -> ToolCallRecord:
    """두 번째 OpenAI 요청에 전달할 가짜 Tool 실행 결과를 만든다."""
    return ToolCallRecord(
        name="get_feeding_schedule",
        arguments={"habitat": "해양관"},
        risk="read",
        result=ToolRunResult(
            success=True,
            data={"habitat": "해양관", "animal": "펭귄"},
            error=None,
            source="fake_mcp",
            retrieved_at=datetime.now(timezone.utc),
        ),
    )


def test_openai_provider_converts_function_call() -> None:
    """OpenAI function_call 응답은 ModelToolCall로 변환되어야 한다."""
    response = SimpleNamespace(
        id="response_1",
        output=[
            SimpleNamespace(
                type="function_call",
                call_id="call_1",
                name="get_feeding_schedule",
                arguments='{"habitat":"해양관"}',
            )
        ],
        output_text="",
    )
    client = FakeOpenAIClient([response])
    provider = OpenAIProvider(
        model="gpt-4.1-mini",
        client=client,
    )

    turn = asyncio.run(
        provider.next_turn(
            question="펭귄 먹이시간 알려줘",
            instructions="도구를 필요할 때만 사용하세요.",
            tools=[FEEDING_TOOL_SCHEMA],
            previous_response_id=None,
            tool_outputs=[],
        )
    )

    assert turn.response_id == "response_1"
    assert turn.calls[0].call_id == "call_1"
    assert turn.calls[0].name == "get_feeding_schedule"
    assert client.responses.requests[0]["parallel_tool_calls"] is False


def test_openai_provider_sends_tool_result_with_matching_call_id() -> None:
    """Tool 결과는 직전 OpenAI Function Call의 call_id로 다시 전달해야 한다."""
    first_response = SimpleNamespace(
        id="response_1",
        output=[
            SimpleNamespace(
                type="function_call",
                call_id="call_1",
                name="get_feeding_schedule",
                arguments='{"habitat":"해양관"}',
            )
        ],
        output_text="",
    )
    second_response = SimpleNamespace(
        id="response_2",
        output=[],
        output_text="다음 펭귄 먹이시간은 14:30입니다.",
    )
    client = FakeOpenAIClient([first_response, second_response])
    provider = OpenAIProvider(
        model="gpt-4.1-mini",
        client=client,
    )

    asyncio.run(
        provider.next_turn(
            question="펭귄 먹이시간 알려줘",
            instructions="도구를 필요할 때만 사용하세요.",
            tools=[FEEDING_TOOL_SCHEMA],
            previous_response_id=None,
            tool_outputs=[],
        )
    )
    final_turn = asyncio.run(
        provider.next_turn(
            question="펭귄 먹이시간 알려줘",
            instructions="도구를 필요할 때만 사용하세요.",
            tools=[FEEDING_TOOL_SCHEMA],
            previous_response_id="response_1",
            tool_outputs=[create_tool_result()],
        )
    )

    second_request = client.responses.requests[1]
    tool_output = second_request["input"][0]

    assert second_request["previous_response_id"] == "response_1"
    assert tool_output["type"] == "function_call_output"
    assert tool_output["call_id"] == "call_1"
    assert json.loads(tool_output["output"])["success"] is True
    assert final_turn.text == "다음 펭귄 먹이시간은 14:30입니다."


def test_openai_provider_converts_clarification_control_tool() -> None:
    """request_clarification은 실행 Tool이 아닌 clarification으로 변환해야 한다."""
    response = SimpleNamespace(
        id="response_1",
        output=[
            SimpleNamespace(
                type="function_call",
                call_id="call_clarification",
                name="request_clarification",
                arguments='{"question":"출발 위치와 목적지를 알려주세요."}',
            )
        ],
        output_text="",
    )
    provider = OpenAIProvider(
        model="gpt-4.1-mini",
        client=FakeOpenAIClient([response]),
    )

    turn = asyncio.run(
        provider.next_turn(
            question="길 알려줘",
            instructions="정보가 부족하면 추가 질문하세요.",
            tools=[],
            previous_response_id=None,
            tool_outputs=[],
        )
    )

    assert turn.calls == []
    assert turn.clarification == "출발 위치와 목적지를 알려주세요."


def test_openai_provider_requires_api_key_without_fake_client() -> None:
    """실제 Client를 생성할 때 API Key가 없으면 즉시 오류를 알려야 한다."""
    with pytest.raises(ValueError):
        OpenAIProvider(model="gpt-4.1-mini")

def test_openai_provider_sends_reservation_tool_schema() -> None:
    """예약 Tool Schema는 OpenAI 요청의 Function Tool 목록에 포함되어야 한다."""
    from backend.app.tools.registry import RESERVATION_TOOL_SCHEMA

    response = SimpleNamespace(
        id="response_reservation",
        output=[],
        output_text="예약 정보를 확인하겠습니다.",
    )
    client = FakeOpenAIClient([response])
    provider = OpenAIProvider(
        model="gpt-4.1-mini",
        client=client,
    )

    asyncio.run(
        provider.next_turn(
            question="내일 15시에 사육사 체험 2명 예약해 줘.",
            instructions="예약은 사용자 확인 전 완료하지 마세요.",
            tools=[RESERVATION_TOOL_SCHEMA],
            previous_response_id=None,
            tool_outputs=[],
        )
    )

    sent_tools = client.responses.requests[0]["tools"]
    reservation_tool = next(
        tool
        for tool in sent_tools
        if tool["name"] == "reserve_experience_program"
    )

    assert reservation_tool["type"] == "function"
    assert reservation_tool["parameters"]["required"] == [
        "program",
        "visit_time",
        "headcount",
    ]
    assert reservation_tool["parameters"]["additionalProperties"] is False