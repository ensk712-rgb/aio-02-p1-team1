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
        if not users.validate_credentials(request.user_id, request.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="아이디 또는 비밀번호가 올바르지 않습니다.",
            )
        return LoginResponse(
            success=True,
            user_id=request.user_id,
            auth_session_id=sessions.create(request.user_id),
        )

    @router.post("/api/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
    async def logout(
        auth_session_id: Annotated[str | None, Header(alias="X-Auth-Session")] = None,
    ) -> None:
        sessions.delete(auth_session_id)

    return router
