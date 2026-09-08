"""Zoo Visit Guide FastAPI 애플리케이션 조립 진입점.

auth/예약 시스템은 이번 로드맵에서 다루지 않으므로 agent/health/admin
Router만 등록한다 (plan.md 2.2절 Out-of-Scope).
"""

from __future__ import annotations

from fastapi import FastAPI

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
from backend.app.routers.admin_router import create_admin_router
from backend.app.routers.agent_router import create_agent_router
from backend.app.routers.health_router import create_health_router
from backend.app.schemas.tools import ToolRunResult as ExecutorToolRunResult
from backend.app.services.agent_orchestration_service import AgentOrchestrationService
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


def create_app(settings: Settings | None = None) -> FastAPI:
    """설정을 조립해 실행 가능한 FastAPI 앱을 만든다."""
    settings = settings or get_settings()

    mcp_client = McpClient(
        settings.MCP_SERVER_URL,
        timeout_seconds=settings.MCP_TIMEOUT_SECONDS,
    )
    executor = ToolExecutor(
        rag_search=_retrieve_animal_info_for_executor,
        mcp_client=mcp_client,
        max_same_tool_calls=settings.MAX_SAME_TOOL_CALLS,
        max_tool_calls=settings.MAX_TOOL_CALLS,
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
    )

    application = FastAPI(title="Zoo Visit Guide API", version="0.1.0")
    application.include_router(create_agent_router(service))
    application.include_router(
        create_health_router(
            mcp_client,
            app_mode=settings.APP_MODE,
            storage=settings.STORAGE_MODE,
            persistence_check=_PersistenceHealth(settings) if settings.STORAGE_MODE == "persistent" else None,
        )
    )
    application.include_router(
        create_admin_router(
            trace_repository.list_runs,
            admin_token=settings.ADMIN_TOKEN,
        )
    )
    return application


def _retrieve_animal_info_for_executor(query: str, collection: str) -> ExecutorToolRunResult:
    """rag_service의 ToolRunResult(schemas.common)를 Executor 계약(schemas.tools)으로 정규화한다."""
    result = retrieve_animal_info(query, collection)
    return ExecutorToolRunResult.model_validate(result.model_dump())


app = create_app()
