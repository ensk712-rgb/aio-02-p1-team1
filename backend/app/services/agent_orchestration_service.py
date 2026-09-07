"""세션, Profile, Runtime, Trace 저장을 조립하는 Agent 서비스다."""

from typing import Protocol

from backend.app.agents.models import AgentProfile
from backend.app.agents.registry import get_agent_profile
from backend.app.agents.runtime import RuntimeSettings, run_agent
from backend.app.providers.base import ModelProvider
from backend.app.schemas.agent import AgentAskRequest, AgentAskResponse
from backend.app.tools.executor import ToolExecutor


class SessionRepositoryProtocol(Protocol):
    """Service가 세션 저장소에 요구하는 최소 기능이다.

    실제 구현은 최두나 담당 Repository가 제공한다.
    """

    def create_session(self) -> str:
        """새로운 서버 발급 세션 ID를 반환한다."""

    def validate_session(self, session_id: str) -> bool:
        """세션 ID가 서버가 발급한 유효한 세션인지 확인한다."""


class TraceRepositoryProtocol(Protocol):
    """Service가 Trace 저장소에 요구하는 최소 기능이다."""

    def save_run(
        self,
        session_id: str,
        run_id: str,
        status: str,
        trace: list[dict],
    ) -> None:
        """실행 결과와 Trace를 저장한다."""


class InvalidSessionError(Exception):
    """클라이언트가 유효하지 않은 세션 ID를 보낸 경우 발생하는 예외다."""


class AgentOrchestrationService:
    """Agent 요청 하나의 실행 순서를 조립하는 P0 Service다."""

    def __init__(
        self,
        *,
        session_repository: SessionRepositoryProtocol,
        trace_repository: TraceRepositoryProtocol,
        provider: ModelProvider,
        executor: ToolExecutor,
        settings: RuntimeSettings,
    ) -> None:
        """Runtime과 저장소 의존성을 생성자에서 주입한다."""
        self._session_repository = session_repository
        self._trace_repository = trace_repository
        self._provider = provider
        self._executor = executor
        self._settings = settings

    async def handle_ask(self, request: AgentAskRequest) -> AgentAskResponse:
        """질문 요청을 실행하고 Trace를 저장한 뒤 API 응답을 반환한다.

        session_id가 없으면 서버가 새 세션을 발급한다.
        session_id가 있으면 저장소에서 유효성을 확인한다.
        """
        session_id = self._resolve_session_id(request.session_id)
        request_with_session = request.model_copy(
            update={"session_id": session_id}
        )
        profile = self._get_profile()

        response = await run_agent(
            request_with_session,
            profile,
            provider=self._provider,
            executor=self._executor,
            settings=self._settings,
        )

        self._trace_repository.save_run(
            session_id=response.session_id,
            run_id=response.run_id,
            status=response.status,
            trace=[item.model_dump(mode="json") for item in response.trace],
        )

        return response

    def _resolve_session_id(self, requested_session_id: str | None) -> str:
        """새 세션을 발급하거나 기존 세션의 유효성을 검사한다."""
        if requested_session_id is None:
            return self._session_repository.create_session()

        if not self._session_repository.validate_session(requested_session_id):
            raise InvalidSessionError("유효하지 않거나 만료된 세션입니다.")

        return requested_session_id

    @staticmethod
    def _get_profile() -> AgentProfile:
        """P0에서 고정된 zoo_guide Profile을 가져온다."""
        return get_agent_profile("zoo_guide")