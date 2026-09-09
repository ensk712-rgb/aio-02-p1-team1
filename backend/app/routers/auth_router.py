"""DB 사용자 1건을 검증하는 최소 로그인 Router."""

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, status

from backend.app.repositories.auth_session_repository import AuthSessionRepository
from backend.app.repositories.user_repository import UserRepository
from backend.app.schemas.auth import LoginRequest, LoginResponse


def create_auth_router(users: UserRepository, sessions: AuthSessionRepository) -> APIRouter:
    router = APIRouter(tags=["auth"])

    @router.post("/api/auth/login", response_model=LoginResponse)
    async def login(request: LoginRequest) -> LoginResponse:
        identity = users.authenticate(request.user_id, request.password)
        if identity is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="아이디 또는 비밀번호가 올바르지 않습니다.",
            )
        return LoginResponse(
            success=True,
            user_id=identity["user_id"],
            role=identity["role"],
            auth_session_id=sessions.create(identity["user_id"], identity["role"]),
        )

    @router.post("/api/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
    async def logout(
        auth_session_id: Annotated[str | None, Header(alias="X-Auth-Session")] = None,
    ) -> None:
        sessions.delete(auth_session_id)

    @router.get("/api/auth/session")
    async def get_session(
        auth_session_id: Annotated[str | None, Header(alias="X-Auth-Session")] = None,
    ) -> dict[str, str | bool]:
        """브라우저에 남은 세션 ID를 검증하고 최소 사용자 정보만 반환한다."""
        user_id = sessions.get_user_id(auth_session_id)
        role = sessions.get_role(auth_session_id)
        if user_id is None or role is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="유효하지 않거나 만료된 세션입니다.",
            )
        return {"success": True, "user_id": user_id, "role": role}

    return router
