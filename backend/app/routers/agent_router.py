"""POST /api/agent/ask 요청을 처리하는 Agent Router를 구현한다."""

from typing import Protocol

from fastapi import APIRouter, HTTPException, status

from backend.app.schemas.agent import AgentAskRequest, AgentAskResponse
from backend.app.services.agent_orchestration_service import InvalidSessionError


class AgentServiceProtocol(Protocol):
    """Router가 Agent Service에 요구하는 최소 기능이다."""

    async def handle_ask(self, request: AgentAskRequest) -> AgentAskResponse:
        """검증된 질문 요청을 실행하고 Agent 응답을 반환한다."""


def create_agent_router(service: AgentServiceProtocol) -> APIRouter:
    """주입받은 Service를 사용하는 Agent API Router를 생성한다.

    main.py가 실제 Service를 생성해 이 함수에 전달한다.
    테스트에서는 Fake Service를 전달할 수 있다.
    """
    router = APIRouter(tags=["agent"])

    @router.post(
        "/api/agent/ask",
        response_model=AgentAskResponse,
        status_code=status.HTTP_200_OK,
    )
    async def ask_agent(request: AgentAskRequest) -> AgentAskResponse:
        """관람객의 질문을 Service에 전달하고 Agent 응답을 반환한다."""
        try:
            return await service.handle_ask(request)
        except InvalidSessionError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="유효하지 않거나 만료된 세션입니다.",
            ) from error
        except Exception as error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="요청 처리 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.",
            ) from error

    return router