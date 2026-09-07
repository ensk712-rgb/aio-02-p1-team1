"""Zoo Visit Guide FastAPI 애플리케이션 조립 진입점."""

from __future__ import annotations

from fastapi import FastAPI

from backend.app.agents.runtime import RuntimeSettings
from backend.app.core.config import Settings, get_settings
from backend.app.mcp_client.client import McpClient
from backend.app.providers.mock_provider import ZooMockProvider
from backend.app.providers.openai_provider import OpenAIProvider
from backend.app.repositories import session_repository, trace_repository
from backend.app.repositories.auth_session_repository import AuthSessionRepository
from backend.app.repositories.reservation_repository import ReservationRepository
from backend.app.repositories.pending_action_repository import PendingActionRepository
from backend.app.repositories.user_repository import UserRepository
from backend.app.routers.admin_router import create_admin_router
from backend.app.routers.agent_router import create_agent_router
from backend.app.routers.auth_router import create_auth_router
from backend.app.routers.health_router import create_health_router
from backend.app.routers.reservation_router import create_reservation_router
from backend.app.services.agent_orchestration_service import AgentOrchestrationService
from backend.app.services.rag_service import retrieve_animal_info
from backend.app.services.approval_service import ApprovalService
from backend.app.schemas.tools import ToolRunResult
from backend.app.tools.executor import ToolExecutor


def create_app(
    settings: Settings | None = None,
    *,
    user_repository: UserRepository | None = None,
    auth_sessions: AuthSessionRepository | None = None,
    reservations: ReservationRepository | None = None,
    pending_actions: PendingActionRepository | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    user_repository = user_repository or UserRepository()
    auth_sessions = auth_sessions or AuthSessionRepository(
        ttl_seconds=settings.SESSION_TTL_SECONDS
    )
    reservations = reservations or ReservationRepository()
    pending_actions = pending_actions or PendingActionRepository(
        ttl_seconds=settings.PENDING_TTL_SECONDS
    )
    approvals = ApprovalService(pending_actions, reservations)
    user_repository.initialize()
    mcp_client = McpClient(
        settings.MCP_SERVER_URL,
        timeout_seconds=settings.MCP_TIMEOUT_SECONDS,
    )
    executor = ToolExecutor(
        rag_search=_retrieve_animal_info_for_executor,
        mcp_client=mcp_client,
        max_same_tool_calls=settings.MAX_SAME_TOOL_CALLS,
        max_tool_calls=settings.MAX_TOOL_CALLS,
        mcp_timeout_seconds=settings.MCP_TIMEOUT_SECONDS,
        mcp_retry_count=settings.MCP_RETRY_COUNT,
    )
    provider = (
        ZooMockProvider()
        if settings.APP_MODE == "mock"
        else OpenAIProvider(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            timeout_seconds=min(30.0, settings.RUN_TIMEOUT_SECONDS),
        )
    )
    service = AgentOrchestrationService(
        session_repository=session_repository,
        trace_repository=trace_repository,
        provider=provider,
        executor=executor,
        settings=RuntimeSettings(
            max_agent_steps=settings.MAX_AGENT_STEPS,
            run_timeout_seconds=settings.RUN_TIMEOUT_SECONDS,
        ),
    )

    application = FastAPI(title="Zoo Visit Guide API", version="0.3.0")
    application.include_router(create_auth_router(user_repository, auth_sessions))
    application.include_router(create_agent_router(service))
    application.include_router(
        create_reservation_router(reservations, auth_sessions, approvals)
    )
    application.include_router(
        create_health_router(
            mcp_client,
            app_mode=settings.APP_MODE,
            storage=settings.STORAGE_MODE,
        )
    )
    application.include_router(
        create_admin_router(
            trace_repository.list_runs,
            admin_token=settings.ADMIN_TOKEN,
            auth_sessions=auth_sessions,
        )
    )
    return application


def _retrieve_animal_info_for_executor(query: str, collection: str) -> ToolRunResult:
    """중복된 기존 Schema 경계를 Executor 표준 ToolRunResult로 정규화한다."""
    result = retrieve_animal_info(query, collection)
    return ToolRunResult.model_validate(result.model_dump())


app = create_app()
