"""Zoo Visit Guide FastAPI 애플리케이션 조립 진입점.

예약은 MCP Server에 등록하지 않는다.
Agent가 예약 Tool을 선택하면 ToolExecutor가 ApprovalService로 전달하고,
ApprovalService는 사용자 확인용 Pending Action만 생성한다.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from backend.app.agents.runtime import RuntimeSettings
from backend.app.core import db as db_module
from backend.app.core import redis_client as redis_client_module
from backend.app.core.config import Settings, get_settings
from backend.app.mcp_client.client import McpClient
from backend.app.providers.mock_provider import ZooMockProvider
from backend.app.providers.openai_provider import OpenAIProvider
from backend.app.repositories import (
    session_memory_repository,
    session_repository,
    trace_repository,
)
from backend.app.repositories.auth_session_repository import AuthSessionRepository
from backend.app.repositories.pending_action_repository import (
    PendingActionRepository,
    PostgresPendingActionRepository,
)
from backend.app.repositories.reservation_repository import (
    PostgresReservationRepository,
    ReservationRepository,
)
from backend.app.repositories.user_repository import UserRepository
from backend.app.routers.admin_router import create_admin_router
from backend.app.routers.agent_router import create_agent_router
from backend.app.routers.auth_router import create_auth_router
from backend.app.routers.health_router import create_health_router
from backend.app.routers.reservation_router import create_reservation_router
from backend.app.routers.tools_router import create_tools_router
from backend.app.schemas.tools import ToolRunResult as ExecutorToolRunResult
from backend.app.services.agent_orchestration_service import AgentOrchestrationService
from backend.app.services.approval_service import ApprovalService
from backend.app.services.rag_service import retrieve_animal_info
from backend.app.tools.executor import ToolExecutor


class _PersistenceHealth:
    """core/db.py, core/redis_client.py의 함수를 health_router 계약으로 묶는다.

    create_app()에 전달된 settings를 명시적으로 넘겨야 한다 — 전역 캐시된
    get_settings()에만 의존하면 테스트 등에서 다른 Settings를 주입해도
    무시되고 원래 프로세스의 DATABASE_URL/REDIS_URL을 보게 된다.

    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def check_postgres(self) -> bool:
        try:
            pool = db_module.get_connection_pool(dsn=self._settings.DATABASE_URL)
            with pool.connection() as conn:
                conn.execute("SELECT 1")
            return True
        except Exception:
            return False

    def check_redis(self) -> bool:
        try:
            client = redis_client_module.get_redis_client(url=self._settings.REDIS_URL)
            return client.ping() is True
        except Exception:
            return False


def create_app(
    settings: Settings | None = None,
    *,
    user_repository: UserRepository | None = None,
    auth_sessions: AuthSessionRepository | None = None,
    reservations: ReservationRepository | None = None,
    pending_actions: PendingActionRepository | None = None,
) -> FastAPI:
    """FastAPI 앱과 모든 의존성을 생성하고 Router를 연결한다.

    예약은 MCP Server에 등록하지 않는다.
    Agent가 예약 Tool을 선택하면 ToolExecutor가 ApprovalService로 전달하고,
    ApprovalService는 사용자 확인용 Pending Action만 생성한다.
    """
    settings = settings or get_settings()

    user_repository = user_repository or UserRepository()
    auth_sessions = auth_sessions or AuthSessionRepository(
        ttl_seconds=settings.SESSION_TTL_SECONDS
    )
    if settings.RESERVATION_STORAGE_MODE == "persistent":
        db_module.ensure_reservation_schema(db_module.get_connection_pool(dsn=settings.DATABASE_URL))

    if reservations is None:
        reservations = (
            PostgresReservationRepository()
            if settings.RESERVATION_STORAGE_MODE == "persistent"
            else ReservationRepository()
        )
    if pending_actions is None:
        pending_actions = (
            PostgresPendingActionRepository(ttl_seconds=settings.PENDING_TTL_SECONDS)
            if settings.RESERVATION_STORAGE_MODE == "persistent"
            else PendingActionRepository(ttl_seconds=settings.PENDING_TTL_SECONDS)
        )

    user_repository.initialize()

    approvals = ApprovalService(
        pending_actions,
        reservations,
    )

    mcp_client = McpClient(
        settings.MCP_SERVER_URL,
        timeout_seconds=settings.MCP_TIMEOUT_SECONDS,
    )

    executor = ToolExecutor(
        rag_search=_retrieve_animal_info_for_executor,
        mcp_client=mcp_client,
        reservation_proposer=approvals.propose_reservation,
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
        session_memory_repository=session_memory_repository,
        provider=provider,
        executor=executor,
        settings=RuntimeSettings(
            max_agent_steps=settings.MAX_AGENT_STEPS,
            run_timeout_seconds=settings.RUN_TIMEOUT_SECONDS,
        ),
        auth_sessions=auth_sessions,
    )

    application = FastAPI(
        title="Zoo Visit Guide API",
        version="0.3.0",
    )
    cors_origins = [
        origin.strip()
        for origin in settings.CORS_ALLOW_ORIGINS.split(",")
        if origin.strip()
    ]
    application.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    application.include_router(
        create_auth_router(
            user_repository,
            auth_sessions,
        )
    )
    application.include_router(create_agent_router(service))
    application.include_router(
        create_reservation_router(
            reservations,
            auth_sessions,
            approvals,
        )
    )
    application.include_router(
        create_health_router(
            mcp_client,
            app_mode=settings.APP_MODE,
            storage=settings.STORAGE_MODE,
            persistence_check=(
                _PersistenceHealth(settings)
                if settings.STORAGE_MODE == "persistent"
                else None
            ),
        )
    )
    application.include_router(
        create_admin_router(
            trace_repository.list_runs,
            admin_token=settings.ADMIN_TOKEN,
            auth_sessions=auth_sessions,
            list_recent_summaries=trace_repository.list_recent_summaries,
            get_summary=trace_repository.get_summary,
        )
    )
    application.include_router(create_tools_router())

    return application


async def _retrieve_animal_info_for_executor(
    query: str,
    collection: str,
) -> ExecutorToolRunResult:
    """RAG 동기 검색을 별도 작업 스레드에서 실행한다."""
    result = await asyncio.to_thread(
        retrieve_animal_info,
        query,
        collection,
    )
    return ExecutorToolRunResult.model_validate(result.model_dump())


app = create_app()
