"""P1 예약 Snapshot의 확인·취소·만료 판정 서비스."""

from __future__ import annotations

from typing import Any, Literal

from backend.app.repositories.pending_action_repository import PendingActionRepository
from backend.app.repositories.reservation_repository import ReservationRepository


class ApprovalError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class ApprovalService:
    def __init__(
        self,
        pending_actions: PendingActionRepository,
        reservations: ReservationRepository,
    ) -> None:
        self._pending_actions = pending_actions
        self._reservations = reservations

    def propose_reservation(
        self, *, session_id: str, user_id: str, program: str, visit_time: str, headcount: int
    ) -> dict[str, Any]:
        arguments = {
            "user_id": user_id,
            "program": program,
            "visit_time": visit_time,
            "headcount": headcount,
        }
        return self._pending_actions.create(
            session_id=session_id,
            tool_name="reserve_experience_program",
            arguments=arguments,
            summary=f"{visit_time} {program} · {headcount}명",
        )

    def decide(
        self, *, action_id: str, session_id: str, decision: Literal["confirm", "cancel"]
    ) -> dict[str, Any]:
        outcome, action = self._pending_actions.decide(
            action_id, session_id=session_id, decision=decision
        )
        if outcome == "session_mismatch":
            raise ApprovalError("SESSION_MISMATCH", "이 작업을 확인할 수 없습니다.")
        if outcome == "not_found":
            raise ApprovalError("ACTION_NOT_FOUND", "확인할 예약 요청이 없습니다.")
        if outcome == "expired":
            raise ApprovalError("ACTION_EXPIRED", "확인 시간이 만료되었습니다. 다시 요청해 주세요.")
        if outcome == "already_processed":
            raise ApprovalError("ACTION_ALREADY_PROCESSED", "이미 처리된 예약 요청입니다.")
        if outcome == "cancelled":
            return {"status": "rejected", "message": "예약 요청을 취소했습니다.", "pending_action": action}

        assert action is not None
        arguments = action["arguments"]
        reservation = self._reservations.create(**arguments)
        completed = self._pending_actions.complete(action_id)
        return {
            "status": "completed",
            "message": "예약 승인 요청을 관리자에게 전달했습니다.",
            "pending_action": completed,
            "reservation": reservation,
        }
