"""관리자 전용 세션 Trace 조회 Router."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Annotated

from fastapi import APIRouter, Header, HTTPException, status

from backend.app.core.auth import AdminAuthenticationError, verify_admin_token
from backend.app.repositories.auth_session_repository import AuthSessionRepository


def create_admin_router(
    list_runs: Callable[[str], list[dict[str, Any]]],
    *,
    admin_token: str,
    auth_sessions: AuthSessionRepository | None = None,
) -> APIRouter:
    router = APIRouter(tags=["admin"])

    @router.get("/api/admin/trace")
    async def get_trace(
        session_id: str,
        authorization: Annotated[str | None, Header()] = None,
        auth_session_id: Annotated[str | None, Header(alias="X-Auth-Session")] = None,
    ) -> dict[str, list[dict[str, Any]]]:
        session_role = auth_sessions.get_role(auth_session_id) if auth_sessions else None
        if auth_session_id and session_role is not None and session_role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="관리자 권한이 필요합니다.",
            )
        if session_role != "admin":
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
