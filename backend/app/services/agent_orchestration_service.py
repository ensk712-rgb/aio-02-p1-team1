"""세션, Profile, Runtime, Trace 저장을 조립하는 Agent 서비스다."""

from __future__ import annotations

from typing import Protocol

from backend.app.agents.models import AgentProfile
from backend.app.agents.registry import get_agent_profile
from backend.app.agents.runtime import RuntimeSettings, run_agent
from backend.app.providers.base import ModelProvider
from backend.app.schemas.agent import AgentAskRequest, AgentAskResponse
from backend.app.tools.executor import ToolExecutor


class SessionRepositoryProtocol(Protocol):
    """대화 세션 저장소가 제공해야 하는 최소 기능이다."""

    def create_session(self) -> str:
        """새 서버 발급 대화 세션 ID를 반환한다."""

    def validate_session(self, session_id: str) -> bool:
        """대화 세션 ID가 유효한지 확인한다."""


class TraceRepositoryProtocol(Protocol):
    """Trace 저장소가 제공해야 하는 최소 기능이다."""

    def save_run(
        self,
        session_id: str,
        run_id: str,
        status: str,
        trace: list[dict],
        *,
        question: str | None = None,
    ) -> None:
        """실행 결과와 Trace를 저장한다."""


class SessionMemoryRepositoryProtocol(Protocol):
    """Service가 세션 대화 기억 저장소에 요구하는 최소 기능이다."""

    def get_recent(self, session_id: str) -> list[dict]:
        """세션의 최근 대화 기록을 오래된 것부터 반환한다."""

    def append_message(self, session_id: str, role: str, text: str) -> None:
        """세션 대화 기록에 메시지 한 건을 추가한다."""


class AuthSessionRepositoryProtocol(Protocol):
    """로그인 세션 저장소가 제공해야 하는 최소 기능이다."""

    def get_user_id(self, auth_session_id: str | None) -> str | None:
        """로그인 세션에 연결된 사용자 ID를 반환한다."""


class InvalidSessionError(Exception):
    """유효하지 않은 대화 세션 ID가 전달될 때 발생하는 예외다."""


class AgentOrchestrationService:
    """Agent 요청 한 건의 실행 순서를 조립하는 서비스다."""

    def __init__(
        self,
        *,
        session_repository: SessionRepositoryProtocol,
        trace_repository: TraceRepositoryProtocol,
        session_memory_repository: SessionMemoryRepositoryProtocol,
        provider: ModelProvider,
        executor: ToolExecutor,
        settings: RuntimeSettings,
        auth_sessions: AuthSessionRepositoryProtocol | None = None,
    ) -> None:
        """Runtime과 저장소 의존성을 생성자에서 주입한다."""
        self._session_repository = session_repository
        self._trace_repository = trace_repository
        self._session_memory_repository = session_memory_repository
        self._provider = provider
        self._executor = executor
        self._settings = settings
        self._auth_sessions = auth_sessions

    async def handle_ask(
        self,
        request: AgentAskRequest,
        *,
        auth_session_id: str | None = None,
    ) -> AgentAskResponse:
        """질문을 실행하고 Trace를 저장한 뒤 API 응답을 반환한다.

        대화 세션은 Trace 연결용이고, 로그인 세션은 예약 사용자 소유권 확인용이다.
        """
        session_id = self._resolve_session_id(request.session_id)
        request_with_session = request.model_copy(
            update={"session_id": session_id}
        )
        profile = self._get_profile()
        history = self._session_memory_repository.get_recent(session_id)

        reservation_user_id = self._resolve_reservation_user_id(
            auth_session_id
        )

        response = await run_agent(
            request_with_session,
            profile,
            provider=self._provider,
            executor=self._executor,
            settings=self._settings,
            conversation_history=history,
            reservation_user_id=reservation_user_id,
            reservation_session_id=(
                auth_session_id if reservation_user_id is not None else None
            ),
        )

        self._trace_repository.save_run(
            session_id=response.session_id,
            run_id=response.run_id,
            status=response.status,
            trace=[item.model_dump(mode="json") for item in response.trace],
            question=request.message,
        )
        self._session_memory_repository.append_message(
            session_id, "user", request.message
        )
        self._session_memory_repository.append_message(
            session_id, "agent", response.final_answer
        )

        return response

    def _resolve_session_id(self, requested_session_id: str | None) -> str:
        """새 대화 세션을 발급하거나 기존 대화 세션을 검증한다."""
        if requested_session_id is None:
            return self._session_repository.create_session()

        if not self._session_repository.validate_session(requested_session_id):
            raise InvalidSessionError("유효하지 않거나 만료된 대화 세션입니다.")

        return requested_session_id

    def _resolve_reservation_user_id(
        self,
        auth_session_id: str | None,
    ) -> str | None:
        """로그인 세션에서 예약 사용자 ID를 안전하게 찾는다."""
        if auth_session_id is None or self._auth_sessions is None:
            return None

        return self._auth_sessions.get_user_id(auth_session_id)

    @staticmethod
    def _get_profile() -> AgentProfile:
        """등록된 zoo_guide Agent Profile을 반환한다."""
        return get_agent_profile("zoo_guide")
