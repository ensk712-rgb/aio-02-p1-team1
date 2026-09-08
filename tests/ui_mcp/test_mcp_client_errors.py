"""MCP 장애/비표준 결과를 성공으로 변환하지 않는지 시험."""

from __future__ import annotations

import json
import asyncio
from types import SimpleNamespace

import pytest

from backend.app.mcp_client.client import McpClient, McpResultError
from backend.app.agents.registry import get_agent_profile
from backend.app.schemas.agent import AgentState
from backend.app.schemas.tools import ToolRunResult
from backend.app.tools.executor import ToolExecutor


def _response(text: str = "{}", *, is_error: bool = False, count: int = 1):
    return SimpleNamespace(
        isError=is_error,
        content=[SimpleNamespace(type="text", text=text) for _ in range(count)],
    )


@pytest.mark.parametrize(
    "response",
    [
        _response(is_error=True),
        _response("not-json"),
        _response(count=0),
        _response(count=2),
        _response(json.dumps({"success": True})),
    ],
)
def test_invalid_mcp_results_raise_safe_error(response) -> None:
    with pytest.raises(McpResultError) as captured:
        McpClient.parse_tool_response(response)
    assert "Traceback" not in str(captured.value)
    assert "not-json" not in str(captured.value)


def test_check_health_returns_false_without_leaking_exception(monkeypatch) -> None:
    client = McpClient("http://127.0.0.1:1/mcp", timeout_seconds=0.01)

    async def fail():
        raise TimeoutError("sensitive-internal-detail")

    monkeypatch.setattr(client, "list_tools", fail)

    assert asyncio.run(client.check_health()) is False


def test_executor_retries_timeout_once_then_returns_error() -> None:
    class SlowMcpClient:
        def __init__(self) -> None:
            self.calls = 0

        async def list_tools(self):
            return []

        async def call_tool(self, name, arguments):
            self.calls += 1
            await asyncio.sleep(0.05)
            raise AssertionError("timeout 전에 취소되어야 합니다")

    slow = SlowMcpClient()
    executor = ToolExecutor(
        rag_search=lambda query, collection: ToolRunResult.model_validate({}),
        mcp_client=slow,
        mcp_timeout_seconds=0.01,
        mcp_retry_count=1,
    )
    state = AgentState(
        run_id="run_timeout",
        agent_id="zoo_guide",
        session_id="session_timeout",
        question="먹이시간",
    )
    result = asyncio.run(
        executor.execute_tool_safely(
            "get_feeding_schedule",
            {"habitat": "해양관"},
            profile=get_agent_profile("zoo_guide"),
            state=state,
        )
    )
    assert result.success is False
    assert result.error is not None and result.error.code == "MCP_TIMEOUT"
    assert slow.calls == 2
    assert state.tool_attempts == 2


def test_executor_invalid_mcp_result_is_error_without_retry() -> None:
    class InvalidMcpClient:
        def __init__(self) -> None:
            self.calls = 0

        async def list_tools(self):
            return []

        async def call_tool(self, name, arguments):
            self.calls += 1
            raise McpResultError("MCP 도구 응답 형식이 올바르지 않습니다.")

    invalid = InvalidMcpClient()
    executor = ToolExecutor(
        rag_search=lambda query, collection: ToolRunResult.model_validate({}),
        mcp_client=invalid,
        mcp_retry_count=1,
    )
    state = AgentState(
        run_id="run_invalid",
        agent_id="zoo_guide",
        session_id="session_invalid",
        question="휴장 여부",
    )
    result = asyncio.run(
        executor.execute_tool_safely(
            "check_closure_status",
            {"habitat": None},
            profile=get_agent_profile("zoo_guide"),
            state=state,
        )
    )
    assert result.success is False
    assert result.data == {}
    assert result.error is not None and result.error.code == "MCP_TOOL_ERROR"
    assert invalid.calls == 1
    assert state.tool_attempts == 1
