"""ToolExecutor의 권한, 입력 검증, 반복 제한을 검증한다."""

import asyncio
from datetime import datetime, timezone
from typing import Any

from backend.app.agents.registry import get_agent_profile
from backend.app.schemas.agent import AgentState
from backend.app.schemas.tools import ToolRunResult
from backend.app.tools.executor import ToolExecutor


class FakeMcpClient:
    """MCP 호출을 기록하고 미리 정한 결과를 반환하는 테스트용 Client다."""

    def __init__(self) -> None:
        """아직 호출되지 않은 빈 기록 목록을 만든다."""
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> ToolRunResult:
        """호출 정보를 기록한 뒤 성공 결과를 반환한다."""
        self.calls.append((name, arguments))

        return ToolRunResult(
            success=True,
            data={"tool_name": name, "arguments": arguments},
            error=None,
            source="fake_mcp",
            retrieved_at=datetime.now(timezone.utc),
        )


def create_fake_rag_search(calls: list[tuple[str, str]]):
    """RAG 검색 호출을 기록하는 테스트용 함수를 만든다."""

    def fake_rag_search(query: str, collection: str) -> ToolRunResult:
        """검색 인자를 기록한 뒤 가짜 성공 결과를 반환한다."""
        calls.append((query, collection))

        return ToolRunResult(
            success=True,
            data={"matched": False, "chunks": []},
            error=None,
            source="fake_rag",
            retrieved_at=datetime.now(timezone.utc),
        )

    return fake_rag_search


def create_state() -> AgentState:
    """각 테스트가 독립적으로 사용할 빈 Agent 실행 상태를 만든다."""
    return AgentState(
        run_id="run_test",
        agent_id="zoo_guide",
        session_id="session_test",
        question="테스트 질문",
    )


def create_executor(
    mcp_client: FakeMcpClient,
    rag_calls: list[tuple[str, str]],
) -> ToolExecutor:
    """테스트 Fake 의존성을 연결한 ToolExecutor를 만든다."""
    return ToolExecutor(
        rag_search=create_fake_rag_search(rag_calls),
        mcp_client=mcp_client,
    )


def test_executor_blocks_unallowed_tool_without_execution() -> None:
    """미허용 Tool은 MCP와 RAG를 전혀 실행하지 않아야 한다."""
    mcp_client = FakeMcpClient()
    rag_calls: list[tuple[str, str]] = []
    executor = create_executor(mcp_client, rag_calls)

    result = asyncio.run(
        executor.execute_tool_safely(
            "delete_database",
            {},
            profile=get_agent_profile("zoo_guide"),
            state=create_state(),
        )
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.code == "TOOL_NOT_ALLOWED"
    assert mcp_client.calls == []
    assert rag_calls == []


def test_executor_blocks_invalid_route_arguments_without_execution() -> None:
    """경로 Tool의 숫자 출발지는 strict 검증에서 차단해야 한다."""
    mcp_client = FakeMcpClient()
    rag_calls: list[tuple[str, str]] = []
    executor = create_executor(mcp_client, rag_calls)

    result = asyncio.run(
        executor.execute_tool_safely(
            "find_habitat_route",
            {"current": 123, "destination": "해양관"},
            profile=get_agent_profile("zoo_guide"),
            state=create_state(),
        )
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.code == "INVALID_TOOL_ARGUMENTS"
    assert mcp_client.calls == []


def test_executor_runs_allowed_mcp_tool() -> None:
    """허용된 Tool과 유효한 인자는 MCP Client에 전달해야 한다."""
    mcp_client = FakeMcpClient()
    rag_calls: list[tuple[str, str]] = []
    executor = create_executor(mcp_client, rag_calls)
    state = create_state()

    result = asyncio.run(
        executor.execute_tool_safely(
            "get_feeding_schedule",
            {"habitat": "해양관"},
            profile=get_agent_profile("zoo_guide"),
            state=state,
        )
    )

    assert result.success is True
    assert mcp_client.calls == [
        ("get_feeding_schedule", {"habitat": "해양관"})
    ]
    assert state.tool_attempts == 1


def test_executor_runs_course_info_tool_with_empty_arguments() -> None:
    """코스 목록 Tool은 빈 인자를 허용하고 MCP에 빈 객체를 전달해야 한다."""
    mcp_client = FakeMcpClient()
    rag_calls: list[tuple[str, str]] = []
    executor = create_executor(mcp_client, rag_calls)
    state = create_state()

    result = asyncio.run(
        executor.execute_tool_safely(
            "get_course_info",
            {},
            profile=get_agent_profile("zoo_guide"),
            state=state,
        )
    )

    assert result.success is True
    assert mcp_client.calls == [("get_course_info", {"name": None})]
    assert state.tool_attempts == 1


def test_executor_blocks_invalid_course_info_arguments_without_execution() -> None:
    """코스 Tool의 계약 밖 인자는 MCP 호출 전에 차단해야 한다."""
    mcp_client = FakeMcpClient()
    rag_calls: list[tuple[str, str]] = []
    executor = create_executor(mcp_client, rag_calls)

    result = asyncio.run(
        executor.execute_tool_safely(
            "get_course_info",
            {"name": "아이동반 코스", "available_minutes": 60},
            profile=get_agent_profile("zoo_guide"),
            state=create_state(),
        )
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.code == "INVALID_TOOL_ARGUMENTS"
    assert mcp_client.calls == []


def test_executor_runs_allowed_rag_tool() -> None:
    """허용된 RAG 검색은 MCP가 아닌 RAG 함수로 실행해야 한다."""
    mcp_client = FakeMcpClient()
    rag_calls: list[tuple[str, str]] = []
    executor = create_executor(mcp_client, rag_calls)

    result = asyncio.run(
        executor.execute_tool_safely(
            "retrieve_animal_info",
            {"query": "호랑이 먹이", "collection": "animal_cards"},
            profile=get_agent_profile("zoo_guide"),
            state=create_state(),
        )
    )

    assert result.success is True
    assert rag_calls == [("호랑이 먹이", "animal_cards")]
    assert mcp_client.calls == []


def test_executor_stops_before_third_same_call() -> None:
    """동일 Tool·동일 인자는 세 번째 실제 실행 전에 차단해야 한다."""
    mcp_client = FakeMcpClient()
    rag_calls: list[tuple[str, str]] = []
    executor = create_executor(mcp_client, rag_calls)
    state = create_state()
    profile = get_agent_profile("zoo_guide")

    asyncio.run(
        executor.execute_tool_safely(
            "get_feeding_schedule",
            {"habitat": "해양관"},
            profile=profile,
            state=state,
        )
    )
    asyncio.run(
        executor.execute_tool_safely(
            "get_feeding_schedule",
            {"habitat": "해양관"},
            profile=profile,
            state=state,
        )
    )
    third_result = asyncio.run(
        executor.execute_tool_safely(
            "get_feeding_schedule",
            {"habitat": "해양관"},
            profile=profile,
            state=state,
        )
    )

    assert third_result.success is False
    assert third_result.error is not None
    assert third_result.error.code == "REPEAT_LIMIT_REACHED"
    assert len(mcp_client.calls) == 2
    assert state.tool_attempts == 2