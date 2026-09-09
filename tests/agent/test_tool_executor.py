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
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> ToolRunResult:
        self.calls.append((name, arguments))

        return ToolRunResult(
            success=True,
            data={"tool_name": name, "arguments": arguments},
            error=None,
            source="fake_mcp",
            retrieved_at=datetime.now(timezone.utc),
        )


def create_fake_rag_search(calls: list[tuple[str, str]]):
    """비동기 RAG 검색 호출을 기록하는 테스트용 함수를 만든다."""

    async def fake_rag_search(
        query: str,
        collection: str,
    ) -> ToolRunResult:
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


def test_executor_runs_course_info_tool_with_available_minutes() -> None:
    """코스 추천 Tool은 기본값까지 채워 MCP에 전달해야 한다."""
    mcp_client = FakeMcpClient()
    rag_calls: list[tuple[str, str]] = []
    executor = create_executor(mcp_client, rag_calls)
    state = create_state()

    result = asyncio.run(
        executor.execute_tool_safely(
            "get_course_info",
            {"available_minutes": 120},
            profile=get_agent_profile("zoo_guide"),
            state=state,
        )
    )

    assert result.success is True
    assert mcp_client.calls == [
        (
            "get_course_info",
            {
                "available_minutes": 120,
                "child_accompanying": False,
                "current": "정문",
            },
        )
    ]
    assert state.tool_attempts == 1


def test_executor_blocks_legacy_course_name_argument() -> None:
    """이전 name 기반 코스 조회 인자는 MCP 호출 전에 차단해야 한다."""
    mcp_client = FakeMcpClient()
    rag_calls: list[tuple[str, str]] = []
    executor = create_executor(mcp_client, rag_calls)

    result = asyncio.run(
        executor.execute_tool_safely(
            "get_course_info",
            {"name": "아이동반 코스"},
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


def test_executor_runs_allowed_get_indoor_course_info() -> None:
    """실내 코스 Tool은 허용된 MCP Tool로 실행돼야 한다."""
    mcp_client = FakeMcpClient()
    executor = create_executor(mcp_client, [])

    result = asyncio.run(
        executor.execute_tool_safely(
            "get_indoor_course_info",
            {
                "available_minutes": 90,
                "child_accompanying": True,
                "current": "정문",
            },
            profile=get_agent_profile("zoo_guide"),
            state=create_state(),
        )
    )

    assert result.success is True
    assert mcp_client.calls[0][0] == "get_indoor_course_info"


def test_executor_runs_allowed_get_outdoor_course_info() -> None:
    """실외 코스 Tool은 허용된 MCP Tool로 실행돼야 한다."""
    mcp_client = FakeMcpClient()
    executor = create_executor(mcp_client, [])

    result = asyncio.run(
        executor.execute_tool_safely(
            "get_outdoor_course_info",
            {"available_minutes": 90},
            profile=get_agent_profile("zoo_guide"),
            state=create_state(),
        )
    )

    assert result.success is True
    assert mcp_client.calls[0][0] == "get_outdoor_course_info"


def test_executor_runs_allowed_lookup_public_weather() -> None:
    """날씨 조회 Tool은 허용된 MCP Tool로 실행돼야 한다."""
    mcp_client = FakeMcpClient()
    executor = create_executor(mcp_client, [])

    result = asyncio.run(
        executor.execute_tool_safely(
            "lookup_public_weather",
            {"region": "서울"},
            profile=get_agent_profile("zoo_guide"),
            state=create_state(),
        )
    )

    assert result.success is True
    assert mcp_client.calls == [
        ("lookup_public_weather", {"region": "서울"})
    ]


def test_executor_blocks_non_integer_available_minutes_without_execution() -> None:
    """available_minutes에 문자열이 오면 MCP를 호출하지 않고 차단해야 한다."""
    mcp_client = FakeMcpClient()
    executor = create_executor(mcp_client, [])

    result = asyncio.run(
        executor.execute_tool_safely(
            "get_course_info",
            {"available_minutes": "백이십분"},
            profile=get_agent_profile("zoo_guide"),
            state=create_state(),
        )
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.code == "INVALID_TOOL_ARGUMENTS"
    assert mcp_client.calls == []


def test_executor_course_info_still_requires_allowlist_entry() -> None:
    """Schema에 등록돼 있어도 Profile allowlist에 없으면 차단해야 한다."""
    mcp_client = FakeMcpClient()
    executor = create_executor(mcp_client, [])
    profile_without_course_tools = get_agent_profile("zoo_guide").model_copy(
        update={"allowed_tools": ()}
    )

    result = asyncio.run(
        executor.execute_tool_safely(
            "get_course_info",
            {"available_minutes": 120},
            profile=profile_without_course_tools,
            state=create_state(),
        )
    )

    assert result.success is False
    assert result.error is not None
    assert result.error.code == "TOOL_NOT_ALLOWED"
    assert mcp_client.calls == []