"""PostgreSQL 예약 저장소의 실제 INSERT와 재생성 후 조회 검증."""

import os

import pytest

from backend.app.core.db import ensure_schema, get_connection_pool
from backend.app.repositories.postgres_reservation_repository import (
    PostgresPendingActionRepository,
    PostgresReservationRepository,
)


pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL이 설정된 PostgreSQL 통합 환경에서 실행",
)


def test_reservation_and_pending_action_survive_repository_recreation() -> None:
    pool = get_connection_pool(os.environ["TEST_DATABASE_URL"])
    ensure_schema(pool)
    reservations = PostgresReservationRepository(pool)
    pending = PostgresPendingActionRepository(ttl_seconds=120, pool=pool)
    user_id = "pytest_persistent_user"
    session_id = "pytest_persistent_session"

    with pool.connection() as conn:
        conn.execute("DELETE FROM reservations WHERE user_id = %s", (user_id,))
        conn.execute("DELETE FROM pending_reservation_actions WHERE session_id = %s", (session_id,))
        conn.commit()

    action = pending.create(
        session_id=session_id,
        tool_name="reserve_experience_program",
        arguments={"user_id": user_id, "program": "사육사 체험", "visit_time": "15:00", "headcount": 2},
        summary="15:00 사육사 체험 · 2명",
    )
    assert PostgresPendingActionRepository(pool=pool).get_pending_for_session(session_id)["action_id"] == action["action_id"]

    outcome, claimed = pending.decide(action["action_id"], session_id=session_id, decision="confirm")
    assert outcome == "ready"
    reservation = reservations.create(**claimed["arguments"])
    pending.complete(action["action_id"])
    recreated = PostgresReservationRepository(pool)
    assert recreated.list_for_user(user_id)[0]["action_id"] == reservation["action_id"]

    with pool.connection() as conn:
        conn.execute("DELETE FROM reservations WHERE user_id = %s", (user_id,))
        conn.execute("DELETE FROM pending_reservation_actions WHERE session_id = %s", (session_id,))
        conn.commit()
