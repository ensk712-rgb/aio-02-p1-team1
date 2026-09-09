"""AgentOrchestrationService의 세션·Runtime·Trace 조립을 검증한다."""

import asyncio
from datetime import datetime, timezone
from typing import Any

import pytest

from backend.app.agents.runtime import RuntimeSettings
from backend.app.providers.mock_provider import ScriptedMockProvider
from backend.app.schemas.agent import AgentAskRequest, ModelTurn
from backend.app.schemas.tools import ToolRunResult
from backend.app.services.agent_orchestration_service import (
    AgentOrchestrationService,
    InvalidSessionError,
)
from backend.app.tools.executor import ToolExecutor


class FakeSessionRepository:
    """세션 발급과 검증을 흉내 내는 테스트용 저장소다."""

    def __init__(self) -> None:
        self.created_sessions: list[str] = []
        self.valid_sessions: set[str] = {"session_existing"}

    def create_session(self) -> str:
        """결정적인 새 세션 ID를 만들고 유효 목록에 넣는다."""
        session_id = f"session_new_{len(self.created_sessions) + 1}"
        self.created_sessions.append(session_id)
        self.valid_sessions.add(session_id)
        return session_id

    def validate_session(self, session_id: str) -> bool:
        """유효 목록에 있는 세션만 참으로 반환한다."""
        return session_id in self.valid_sessions


class FakeTraceRepository:
    """저장 요청을 메모리에 기록하는 테스트용 Trace 저장소다."""

    def __init__(self) -> None:
        self.saved_runs: list[dict[str, Any]] = []

    def save_run(
        self,
        session_id: str,
        run_id: str,
        status: str,
        trace: list[dict],
        *,
        question: str | None = None,
    ) -> None:
        """저장하려는 값을 검증용 목록에 추가한다."""
        self.saved_runs.append(
            {
                "session_id": session_id,
                "run_id": run_id,
                "status": status,
                "trace": trace,
                "question": question,
            }
        )


class FakeMcpClient:
    """Tool 호출 없이 최종 답변만 만드는 테스트에 필요한 최소 MCP Client다."""

    async def list_tools(self) -> list[dict[str, Any]]:
        """MCP Tool이 없는 목록을 반환한다."""
        return []

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> ToolRunResult:
        """이 테스트에서는 MCP 실행이 발생하면 실패시킨다."""
        raise AssertionError(f"예상하지 못한 MCP 호출: {name}, {arguments}")


class FakeSessionMemoryRepository:
    """대화 기억 조회/저장을 흉내 내는 테스트용 저장소다."""

    def __init__(self) -> None:
        self.stored: dict[str, list[dict]] = {}

    def get_recent(self, session_id: str) -> list[dict]:
        return self.stored.get(session_id, [])

    def append_message(self, session_id: str, role: str, text: str) -> None:
        self.stored.setdefault(session_id, []).append({"role": role, "text": text})


def create_service(
    *,
    session_repository: FakeSessionRepository,
    trace_repository: FakeTraceRepository,
    provider: ScriptedMockProvider,
    session_memory_repository: FakeSessionMemoryRepository | None = None,
) -> AgentOrchestrationService:
    """테스트 Fake 의존성을 조립한 Service를 생성한다."""

    def fake_rag_search(query: str, collection: str) -> ToolRunResult:
        """이 테스트에서는 RAG 실행이 발생하면 실패시킨다."""
        raise AssertionError(f"예상하지 못한 RAG 호출: {query}, {collection}")

    executor = ToolExecutor(
        rag_search=fake_rag_search,
        mcp_client=FakeMcpClient(),
    )

    return AgentOrchestrationService(
        session_repository=session_repository,
        trace_repository=trace_repository,
        session_memory_repository=session_memory_repository or FakeSessionMemoryRepository(),
        provider=provider,
        executor=executor,
        settings=RuntimeSettings(),
    )


def test_service_creates_session_and_saves_trace() -> None:
    """세션 없는 첫 요청은 새 세션 발급 후 Trace를 저장해야 한다."""
    session_repository = FakeSessionRepository()
    trace_repository = FakeTraceRepository()
    service = create_service(
        session_repository=session_repository,
        trace_repository=trace_repository,
        provider=ScriptedMockProvider(
            [ModelTurn(response_id="response_1", text="안녕하세요.")]
        ),
    )

    response = asyncio.run(
        service.handle_ask(AgentAskRequest(message="안녕"))
    )

    assert response.status == "completed"
    assert response.session_id == "session_new_1"
    assert session_repository.created_sessions == ["session_new_1"]
    assert len(trace_repository.saved_runs) == 1
    assert trace_repository.saved_runs[0]["run_id"] == response.run_id
    assert trace_repository.saved_runs[0]["status"] == "completed"


def test_service_accepts_server_issued_existing_session() -> None:
    """서버가 이미 발급한 세션은 새 세션 없이 그대로 사용해야 한다."""
    session_repository = FakeSessionRepository()
    trace_repository = FakeTraceRepository()
    service = create_service(
        session_repository=session_repository,
        trace_repository=trace_repository,
        provider=ScriptedMockProvider(
            [ModelTurn(response_id="response_1", text="도와드리겠습니다.")]
        ),
    )

    response = asyncio.run(
        service.handle_ask(
            AgentAskRequest(
                message="동물원 이용 안내를 알려줘",
                session_id="session_existing",
            )
        )
    )

    assert response.session_id == "session_existing"
    assert session_repository.created_sessions == []
    assert trace_repository.saved_runs[0]["session_id"] == "session_existing"


def test_service_rejects_invalid_session_before_runtime() -> None:
    """위조 또는 만료된 세션은 Provider와 Runtime 실행 전에 차단해야 한다."""
    session_repository = FakeSessionRepository()
    trace_repository = FakeTraceRepository()
    provider = ScriptedMockProvider(
        [ModelTurn(response_id="response_1", text="실행되면 안 되는 답변")]
    )
    service = create_service(
        session_repository=session_repository,
        trace_repository=trace_repository,
        provider=provider,
    )

    with pytest.raises(InvalidSessionError):
        asyncio.run(
            service.handle_ask(
                AgentAskRequest(
                    message="질문",
                    session_id="session_forged",
                )
            )
        )

    assert provider.remaining_turns == 1
    assert trace_repository.saved_runs == []


def test_service_reads_and_appends_session_memory() -> None:
    """handle_ask는 실행 전 history를 읽고, 실행 후 질문/답변을 저장해야 한다."""
    session_repository = FakeSessionRepository()
    trace_repository = FakeTraceRepository()
    session_memory_repository = FakeSessionMemoryRepository()
    session_memory_repository.stored["session_existing"] = [
        {"role": "user", "text": "호랑이는 어디 살아?"}
    ]

    service = create_service(
        session_repository=session_repository,
        trace_repository=trace_repository,
        provider=ScriptedMockProvider(
            [ModelTurn(response_id="response_1", text="맹수관에서 서식합니다.")]
        ),
        session_memory_repository=session_memory_repository,
    )

    response = asyncio.run(
        service.handle_ask(
            AgentAskRequest(message="먹이는 뭐 먹어?", session_id="session_existing")
        )
    )

    stored = session_memory_repository.stored["session_existing"]
    assert stored[-2] == {"role": "user", "text": "먹이는 뭐 먹어?"}
    assert stored[-1] == {"role": "agent", "text": response.final_answer}
