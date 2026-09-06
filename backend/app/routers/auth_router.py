"""DB 값 일치만 확인하는 최소 로그인 Router."""

from fastapi import APIRouter, HTTPException, status

from ..auth.repository import UserRepository, default_repository
from ..schemas.auth import LoginRequest, LoginResponse


def create_auth_router(repository: UserRepository | None = None) -> APIRouter:
    router = APIRouter(prefix="/api/auth", tags=["로그인"])

    @router.post("/login", response_model=LoginResponse)
    def login(payload: LoginRequest) -> LoginResponse:
        store = repository or default_repository()
        if not store.authenticate(payload.user_id, payload.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="아이디 또는 비밀번호가 올바르지 않습니다.",
            )
        return LoginResponse(authenticated=True, user_id=payload.user_id)

    return router


auth_router = create_auth_router()
