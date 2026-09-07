"""관리자 전용 세션 Trace 조회 Router."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Annotated

from fastapi import APIRouter, Header, HTTPException, status

from backend.app.core.auth import AdminAuthenticationError, verify_admin_token


def create_admin_router(
    list_runs: Callable[[str], list[dict[str, Any]]],
    *,
    admin_token: str,
) -> APIRouter:
    router = APIRouter(tags=["admin"])

    @router.get("/api/admin/trace")
    async def get_trace(
        session_id: str,
        authorization: Annotated[str | None, Header()] = None,
    ) -> dict[str, list[dict[str, Any]]]:
        try:
            verify_admin_token(authorization, admin_token)
        except AdminAuthenticationError as error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(error),
                headers={"WWW-Authenticate": "Bearer"},
            ) from error
        return {"runs": list_runs(session_id)}

    return router
