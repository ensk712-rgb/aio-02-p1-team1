"""관리자 토큰으로 보호되는 Trace 조회 Router."""

import os
from collections.abc import Callable

from fastapi import APIRouter, Header, HTTPException, status


def _default_list_runs(session_id: str) -> list[dict]:
    try:
        from backend.app.repositories.trace_repository import list_runs
    except ImportError as error:
        raise HTTPException(status_code=503, detail="Trace 저장소를 사용할 수 없습니다.") from error
    return list_runs(session_id)


def create_admin_router(list_runs: Callable[[str], list[dict]] = _default_list_runs) -> APIRouter:
    router = APIRouter(prefix="/api/admin", tags=["관리자"])

    @router.get("/trace")
    def trace(session_id: str, authorization: str | None = Header(default=None)) -> dict:
        token = os.getenv("ADMIN_TOKEN", "")
        if not token or authorization != f"Bearer {token}":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="관리자 인증이 필요합니다.")
        return {"runs": list_runs(session_id)}

    return router


admin_router = create_admin_router()
