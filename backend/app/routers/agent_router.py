"""POST /api/agent/ask 요청을 처리하는 Agent Router를 구현한다."""

from typing import Annotated, Protocol

from fastapi import APIRouter, Header, HTTPException, status

from backend.app.schemas.agent import AgentAskRequest, AgentAskResponse
from backend.app.services.agent_orchestration_service import InvalidSessionError


class AgentServiceProtocol(Protocol):
    """Router가 Agent Service에 요청하는 최소 기능이다."""

    async def handle_ask(
        self,
        request: AgentAskRequest,
        *,
        auth_session_id: str | None = None,
    ) -> AgentAskResponse:
        """검증된 질문 요청을 실행하고 Agent 응답을 반환한다."""


def create_agent_router(service: AgentServiceProtocol) -> APIRouter:
    """주입받은 Service를 사용하는 Agent API Router를 생성한다.

    질문 JSON의 ``session_id``는 대화 세션이다.
    ``X-Auth-Session`` 헤더는 로그인 세션이며 예약 소유권 확인에만 사용한다.
    """
    router = APIRouter(tags=["agent"])

    @router.post(
        "/api/agent/ask",
        response_model=AgentAskResponse,
        status_code=status.HTTP_200_OK,
    )
    async def ask_agent(
        request: AgentAskRequest,
        auth_session_id: Annotated[
            str | None,
            Header(alias="X-Auth-Session"),
        ] = None,
    ) -> AgentAskResponse:
        """질문과 선택적 로그인 세션을 Agent Service로 전달한다."""
        try:
            # 로그인 헤더가 없는 기존 P0 질문은 이전 호출 방식도 유지한다.
            # 따라서 기존 Fake Service 기반 테스트와 호환된다.
            if auth_session_id is None:
                return await service.handle_ask(request)

            return await service.handle_ask(
                request,
                auth_session_id=auth_session_id,
            )
        except InvalidSessionError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="유효하지 않거나 만료된 세션입니다.",
            ) from error
        except Exception as error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    "요청 처리 중 문제가 발생했습니다. "
                    "잠시 후 다시 시도해 주세요."
                ),
            ) from error

    return router