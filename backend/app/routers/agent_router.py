"""레인저 에이전트의 단일 HTTP 진입점입니다.

Router는 요청 검증과 오류 변환만 담당합니다 — 경로 판단, 정책, Tool 실행은 모두
`services.agent_orchestration_service`가 소유합니다.
"""

from fastapi import APIRouter, HTTPException

from app.schemas.agent import AgentAskRequest, AgentAskResponse, AgentConfirmRequest
from app.services import agent_orchestration_service

agent_router = APIRouter(prefix="/api/agent", tags=["레인저 에이전트"])


@agent_router.post("/ask", response_model=AgentAskResponse)
def ask(payload: AgentAskRequest) -> AgentAskResponse:
    try:
        result = agent_orchestration_service.handle_ask(payload.message, payload.session_id)
        return AgentAskResponse.model_validate(result)
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"요청 처리에 실패했어요: {error}") from error


@agent_router.post("/confirm", response_model=AgentAskResponse)
def confirm(payload: AgentConfirmRequest) -> AgentAskResponse:
    try:
        result = agent_orchestration_service.confirm_pending_action(payload.action_id, payload.session_id)
        return AgentAskResponse.model_validate(result)
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"확인 처리에 실패했어요: {error}") from error
