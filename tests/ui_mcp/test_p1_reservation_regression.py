"""Phase 9 P1 승인 경합·소유권 회귀 시험."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.app.repositories.pending_action_repository import PendingActionRepository
from backend.app.repositories.reservation_repository import ReservationRepository
from backend.app.services.approval_service import ApprovalError, ApprovalService


def _service() -> tuple[ApprovalService, ReservationRepository]:
    reservations = ReservationRepository()
    return ApprovalService(PendingActionRepository(ttl_seconds=120), reservations), reservations


def _propose(service: ApprovalService) -> dict:
    return service.propose_reservation(
        session_id="session_a",
        user_id="TEST",
        program="사육사 체험",
        visit_time="15:00",
        headcount=2,
    )


def test_session_mismatch_does_not_consume_original_action() -> None:
    service, reservations = _service()
    action = _propose(service)

    with pytest.raises(ApprovalError) as blocked:
        service.decide(action_id=action["action_id"], session_id="session_b", decision="confirm")
    assert blocked.value.code == "SESSION_MISMATCH"
    assert reservations.list_pending() == []

    accepted = service.decide(
        action_id=action["action_id"], session_id="session_a", decision="confirm"
    )
    assert accepted["status"] == "completed"
    assert len(reservations.list_pending()) == 1


def test_simultaneous_confirm_and_cancel_has_one_terminal_winner() -> None:
    service, reservations = _service()
    action = _propose(service)

    def decide(decision: str) -> str:
        try:
            result = service.decide(
                action_id=action["action_id"],
                session_id="session_a",
                decision=decision,
            )
            return result["status"]
        except ApprovalError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(decide, ["confirm", "cancel"]))

    terminal_winners = [value for value in outcomes if value in {"completed", "rejected"}]
    assert len(terminal_winners) == 1
    assert "ACTION_ALREADY_PROCESSED" in outcomes
    assert len(reservations.list_pending()) in {0, 1}
