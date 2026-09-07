"""Agent Runtime의 Provider → Tool → Provider 반복 흐름을 검증한다."""

import asyncio
from datetime import datetime, timezone
from typing import Any

from backend.app.agents.registry import get_agent_profile
from backend.app.agents.runtime import RuntimeSettings, run_agent
from backend.app.providers.mock_provider import ScriptedMockProvider
from backend.app.schemas.agent import AgentAskRequest, ModelToolCall, ModelTurn
from backend.app.schemas.tools import ToolRunResult
from backend.app.tools.executor import ToolExecutor


class FakeMcpClient:
    """Runtime 테스트용 MCP Client다."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def list_tools(self) -> list[dict[str, Any]]:
        """Provider에 공개할 MCP Tool 목록을 반환한다."""
        return [
            {
                "name": "get_feeding_schedule",
                "description": "먹이시간을 조회한다.",
                "input_schema": {
                    "type": "object",
                    "properties": {"habitat": {"type": "string"}},
                    "required": ["habitat"],
                },
            }
        ]

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> ToolRunResult:
        """MCP 호출을 기록하고 성공 결과를 반환한다."""
        self.calls.append((name, arguments))

        return ToolRunResult(
            success=True,
            data={"habitat": "해양관", "animal": "펭귄"},
            error=None,
            source="fake_mcp",
            retrieved_at=datetime.now(timezone.utc),
        )


def create_executor(mcp_client: FakeMcpClient) -> ToolExecutor:
    """Fake MCP와 Fake RAG를 연결한 Executor를 만든다."""
    def fake_rag_search(query: str, collection: str) -> ToolRunResult:
        """RAG 호출에 사용할 가짜 검색 결과를 반환한다."""
        return ToolRunResult(
            success=True,
            data={"matched": False, "chunks": []},
            error=None,
            source="fake_rag",
            retrieved_at=datetime.now(timezone.utc),
        )

    return ToolExecutor(rag_search=fake_rag_search, mcp_client=mcp_client)


def test_runtime_returns_final_answer_after_tool_result() -> None:
    """Runtime은 Tool 결과를 Provider에 전달한 뒤 최종 답변을 받아야 한다."""
    mcp_client = FakeMcpClient()
    provider = ScriptedMockProvider(
        [
            ModelTurn(
                response_id="response_1",
                calls=[
                    ModelToolCall(
                        call_id="call_1",
                        name="get_feeding_schedule",
                        arguments_json='{"habitat": "해양관"}',
                    )
                ],
            ),
            ModelTurn(
                response_id="response_2",
                text="다음 펭귄 먹이시간은 14:30입니다.",
            ),
        ]
    )

    response = asyncio.run(
        run_agent(
            AgentAskRequest(message="펭귄 먹이시간 알려줘"),
            get_agent_profile("zoo_guide"),
            provider=provider,
            executor=create_executor(mcp_client),
            settings=RuntimeSettings(),
        )
    )

    assert response.status == "completed"
    assert response.intent == "tool"
    assert len(response.tool_calls) == 1
    assert mcp_client.calls == [
        ("get_feeding_schedule", {"habitat": "해양관"})
    ]
    assert provider.call_history[1].tool_result_names == ("get_feeding_schedule",)


def test_runtime_returns_clarification_without_tool_execution() -> None:
    """Provider가 추가 정보를 요청하면 Tool을 실행하지 않아야 한다."""
    mcp_client = FakeMcpClient()
    provider = ScriptedMockProvider(
        [
            ModelTurn(
                response_id="response_1",
                clarification="출발 위치와 목적지를 함께 알려주세요.",
            )
        ]
    )

    response = asyncio.run(
        run_agent(
            AgentAskRequest(message="길 알려줘"),
            get_agent_profile("zoo_guide"),
            provider=provider,
            executor=create_executor(mcp_client),
            settings=RuntimeSettings(),
        )
    )

    assert response.status == "needs_clarification"
    assert response.tool_calls == []
    assert mcp_client.calls == []


def test_runtime_rejects_unallowed_tool_without_mcp_execution() -> None:
    """Profile에 없는 Tool은 Executor가 차단하고 Runtime은 rejected로 끝낸다."""
    mcp_client = FakeMcpClient()
    provider = ScriptedMockProvider(
        [
            ModelTurn(
                response_id="response_1",
                calls=[
                    ModelToolCall(
                        call_id="call_1",
                        name="delete_database",
                        arguments_json="{}",
                    )
                ],
            )
        ]
    )

    response = asyncio.run(
        run_agent(
            AgentAskRequest(message="데이터를 삭제해줘"),
            get_agent_profile("zoo_guide"),
            provider=provider,
            executor=create_executor(mcp_client),
            settings=RuntimeSettings(),
        )
    )

    assert response.status == "rejected"
    assert response.tool_calls == []
    assert mcp_client.calls == []


def test_runtime_stops_before_third_same_tool_call() -> None:
    """같은 Tool과 인자를 세 번째로 실행하기 전에 stopped로 끝내야 한다."""
    mcp_client = FakeMcpClient()
    repeated_call = ModelToolCall(
        call_id="call_repeat",
        name="get_feeding_schedule",
        arguments_json='{"habitat": "해양관"}',
    )
    provider = ScriptedMockProvider(
        [
            ModelTurn(response_id="response_1", calls=[repeated_call]),
            ModelTurn(response_id="response_2", calls=[repeated_call]),
            ModelTurn(response_id="response_3", calls=[repeated_call]),
        ]
    )

    response = asyncio.run(
        run_agent(
            AgentAskRequest(message="펭귄 먹이시간 알려줘"),
            get_agent_profile("zoo_guide"),
            provider=provider,
            executor=create_executor(mcp_client),
            settings=RuntimeSettings(),
        )
    )

    assert response.status == "stopped"
    assert response.termination_reason == "repeat_limit_reached"
    assert len(mcp_client.calls) == 2