"""Backend와 MCP의 상태를 분리해 보여주는 health Router."""

import os

from fastapi import APIRouter, Response, status

from backend.app.mcp_client.client import McpClient

health_router = APIRouter(tags=["상태"])


@health_router.get("/api/health")
async def health(response: Response) -> dict:
    mcp_ok = await McpClient().check_health()
    body = {
        "status": "ok" if mcp_ok else "degraded",
        "backend": "ok",
        "mcp": "ok" if mcp_ok else "unavailable",
        "storage": os.getenv("STORAGE_MODE", "memory"),
        "app_mode": os.getenv("APP_MODE", "mock"),
    }
    if not mcp_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return body
