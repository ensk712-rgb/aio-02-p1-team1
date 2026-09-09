"""사용자 예약 요청과 관리자 승인 Router."""

from typing import Annotated, Any

from fastapi import APIRouter, Header, HTTPException, status

from backend.app.repositories.auth_session_repository import AuthSessionRepository
from backend.app.repositories.reservation_repository import ReservationRepository
from backend.app.schemas.reservation import (
    ReservationConfirmRequest,
    ReservationDecisionRequest,
    ReservationRequest,
)
from backend.app.services.approval_service import ApprovalError, ApprovalService


def create_reservation_router(
    reservations: ReservationRepository,
    sessions: AuthSessionRepository,
    approvals: ApprovalService,
) -> APIRouter:
    router = APIRouter(tags=["reservations"])

    def require_user(auth_session_id: str | None) -> str:
        user_id = sessions.get_user_id(auth_session_id)
        if user_id is None:
            raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
        return user_id

    def require_admin(auth_session_id: str | None) -> str:
        user_id = require_user(auth_session_id)
        if not sessions.is_admin(auth_session_id):
            raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
        return user_id

    @router.post("/api/reservations", status_code=status.HTTP_201_CREATED)
    async def create_reservation(
        request: ReservationRequest,
        auth_session_id: Annotated[str | None, Header(alias="X-Auth-Session")] = None,
    ) -> dict[str, Any]:
        user_id = require_user(auth_session_id)
        pending_action = approvals.propose_reservation(
            session_id=auth_session_id,
            user_id=user_id,
            program=request.program,
            visit_time=request.visit_time,
            headcount=request.headcount,
        )
        return {
            "status": "confirmation_required",
            "message": "예약 내용을 확인해 주세요.",
            "pending_action": pending_action,
        }

    @router.post("/api/agent/confirm")
    async def confirm_reservation(
        request: ReservationConfirmRequest,
        auth_session_id: Annotated[str | None, Header(alias="X-Auth-Session")] = None,
    ) -> dict[str, Any]:
        require_user(auth_session_id)
        if request.session_id != auth_session_id:
            raise HTTPException(status_code=403, detail="이 작업을 확인할 수 없습니다.")
        try:
            return approvals.decide(
                action_id=request.action_id,
                session_id=request.session_id,
                decision=request.decision,
            )
        except ApprovalError as error:
            status_code = 403 if error.code == "SESSION_MISMATCH" else 409
            raise HTTPException(status_code=status_code, detail=str(error)) from error

    @router.get("/api/reservations/mine")
    async def my_reservations(
        auth_session_id: Annotated[str | None, Header(alias="X-Auth-Session")] = None,
    ) -> dict[str, list[dict[str, Any]]]:
        return {"items": reservations.list_for_user(require_user(auth_session_id))}

    @router.get("/api/admin/reservations/pending")
    async def pending_reservations(
        auth_session_id: Annotated[str | None, Header(alias="X-Auth-Session")] = None,
    ) -> dict[str, list[dict[str, Any]]]:
        require_admin(auth_session_id)
        return {"items": reservations.list_pending()}

    @router.post("/api/admin/reservations/{action_id}/decision")
    async def decide_reservation(
        action_id: str,
        request: ReservationDecisionRequest,
        auth_session_id: Annotated[str | None, Header(alias="X-Auth-Session")] = None,
    ) -> dict[str, Any]:
        require_admin(auth_session_id)
        result = reservations.decide(action_id, request.decision)
        if result is None:
            raise HTTPException(status_code=409, detail="이미 처리됐거나 존재하지 않는 요청입니다.")
        return result

    return router
