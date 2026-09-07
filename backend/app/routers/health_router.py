"""Backend와 MCP 상태를 구분해 반환하는 health Router."""

from __future__ import annotations

from typing import Literal, Protocol

from fastapi import APIRouter
from fastapi.responses import JSONResponse


class McpHealthProtocol(Protocol):
    async def check_health(self) -> bool: ...


def create_health_router(
    mcp_client: McpHealthProtocol,
    *,
    app_mode: Literal["mock", "openai"],
    storage: Literal["memory"] = "memory",
) -> APIRouter:
    router = APIRouter(tags=["health"])

    @router.get("/api/health")
    async def health() -> JSONResponse:
        mcp_ok = await mcp_client.check_health()
        payload = {
            "status": "ok" if mcp_ok else "degraded",
            "backend": "ok",
            "mcp": "ok" if mcp_ok else "unavailable",
            "storage": storage,
            "app_mode": app_mode,
        }
        return JSONResponse(status_code=200 if mcp_ok else 503, content=payload)

    return router
