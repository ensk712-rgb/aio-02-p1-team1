"""Backend와 MCP 상태를 구분해 반환하는 health Router."""

from __future__ import annotations

from typing import Literal, Protocol

from fastapi import APIRouter
from fastapi.responses import JSONResponse


class McpHealthProtocol(Protocol):
    async def check_health(self) -> bool: ...


class PersistenceHealthProtocol(Protocol):
    def check_postgres(self) -> bool: ...
    def check_redis(self) -> bool: ...


def create_health_router(
    mcp_client: McpHealthProtocol,
    *,
    app_mode: Literal["mock", "openai"],
    storage: Literal["memory", "persistent"] = "memory",
    persistence_check: PersistenceHealthProtocol | None = None,
) -> APIRouter:
    router = APIRouter(tags=["health"])

    @router.get("/api/health")
    async def health() -> JSONResponse:
        mcp_ok = await mcp_client.check_health()
        payload: dict[str, object] = {
            "status": "ok" if mcp_ok else "degraded",
            "backend": "ok",
            "mcp": "ok" if mcp_ok else "unavailable",
            "storage": storage,
            "app_mode": app_mode,
        }
        status_code = 200 if mcp_ok else 503

        if storage == "persistent" and persistence_check is not None:
            postgres_ok = persistence_check.check_postgres()
            redis_ok = persistence_check.check_redis()
            payload["postgres"] = "ok" if postgres_ok else "unavailable"
            payload["redis"] = "ok" if redis_ok else "unavailable"
            if not (postgres_ok and redis_ok):
                status_code = 503
                payload["status"] = "degraded"

        return JSONResponse(status_code=status_code, content=payload)

    return router
