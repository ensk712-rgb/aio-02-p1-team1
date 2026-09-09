"""관리자 전용 세션 Trace 조회 Router."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Annotated, Protocol

from fastapi import APIRouter, Header, HTTPException, status

from backend.app.core.auth import AdminAuthenticationError, verify_admin_token


class AuthSessionRoleLookup(Protocol):
    """관리자 라우터가 로그인 세션 저장소에 요구하는 최소 기능이다.

    로그인/권한 시스템(AuthSessionRepository)은 이번 로드맵 범위 밖이라
    구체 클래스를 import하지 않고 구조적 타입으로만 받는다.
    """

    def get_role(self, auth_session_id: str | None) -> str | None: ...


def create_admin_router(
    list_runs: Callable[[str], list[dict[str, Any]]],
    *,
    admin_token: str,
    auth_sessions: AuthSessionRoleLookup | None = None,
    list_recent_summaries: Callable[[], list[dict[str, Any]]] | None = None,
    get_summary: Callable[[str], dict[str, Any] | None] | None = None,
) -> APIRouter:
    router = APIRouter(tags=["admin"])

    @router.get("/api/admin/trace")
    async def get_trace(
        session_id: str,
        authorization: Annotated[str | None, Header()] = None,
        auth_session_id: Annotated[str | None, Header(alias="X-Auth-Session")] = None,
    ) -> dict[str, Any]:
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
        runs = list_runs(session_id)
        summary = get_summary(session_id) if get_summary else None
        return {
            "session_id": session_id,
            "runs": runs,
            "detail_expired": bool(summary) and not runs,
            "summary": summary,
        }

    @router.get("/api/admin/trace/sessions")
    async def list_recent_trace_sessions(
        authorization: Annotated[str | None, Header()] = None,
        auth_session_id: Annotated[str | None, Header(alias="X-Auth-Session")] = None,
    ) -> dict[str, Any]:
        session_role = auth_sessions.get_role(auth_session_id) if auth_sessions else None
        if auth_session_id and session_role is not None and session_role != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="관리자 권한이 필요합니다.")
        if session_role != "admin":
            try:
                verify_admin_token(authorization, admin_token)
            except AdminAuthenticationError as error:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=str(error),
                    headers={"WWW-Authenticate": "Bearer"},
                ) from error
        return {"sessions": list_recent_summaries() if list_recent_summaries else []}

    return router
