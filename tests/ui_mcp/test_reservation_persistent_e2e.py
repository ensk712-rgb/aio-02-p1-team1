"""RESERVATION_STORAGE_MODE=persistent로 실제 서버를 띄워 예약 전체 흐름을 검증한다.

로그인 → 예약 요청(확인대기 생성) → 사용자 확인(예약 행 생성) → 관리자 승인
→ 사용자 조회까지, 전부 Postgres에 실제로 저장된 값으로 확인한다.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import Settings

pytestmark = pytest.mark.integration


@pytest.fixture()
def client():
    from backend.app.core import db as db_module
    from backend.app.main import create_app
    from backend.app.repositories.user_repository import UserRepository

    db_module._reset_pool_for_tests()
    settings = Settings(
        _env_file=None,
        APP_MODE="mock",
        RESERVATION_STORAGE_MODE="persistent",
        DATABASE_URL="postgresql://zoo:zoo@127.0.0.1:5432/zoo",
        MCP_SERVER_URL="http://127.0.0.1:1/mcp",  # 이 시나리오는 MCP를 쓰지 않는다
    )

    # 시험용 예약만 지워 다른 통합 테스트와 상태가 섞이지 않게 한다.
    pool = db_module.get_connection_pool(dsn=settings.DATABASE_URL)
    db_module.ensure_reservation_schema(pool)
    with pool.connection() as conn:
        conn.execute("DELETE FROM pending_reservation_actions")
        conn.execute("DELETE FROM reservations")
        conn.commit()

    with TestClient(create_app(settings)) as test_client:
        yield test_client

    with pool.connection() as conn:
        conn.execute("DELETE FROM pending_reservation_actions")
        conn.execute("DELETE FROM reservations")
        conn.commit()


def _login(client: TestClient, user_id: str, password: str) -> str:
    response = client.post("/api/auth/login", json={"user_id": user_id, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["auth_session_id"]


def test_reservation_full_flow_persists_through_postgres(client: TestClient) -> None:
    user_session = _login(client, "TEST", "1234")
    admin_session = _login(client, "admin", "1234")

    # 1) 사용자가 예약을 요청하면 확인대기(pending_action)가 생긴다.
    create_response = client.post(
        "/api/reservations",
        headers={"X-Auth-Session": user_session},
        json={"program": "사육사 체험", "visit_time": "15:00", "headcount": 2},
    )
    assert create_response.status_code == 201, create_response.text
    body = create_response.json()
    assert body["status"] == "confirmation_required"
    action_id = body["pending_action"]["action_id"]

    # 2) 사용자가 확인하면 실제 예약 행(reservations)이 Postgres에 생성된다.
    confirm_response = client.post(
        "/api/agent/confirm",
        headers={"X-Auth-Session": user_session},
        json={"action_id": action_id, "session_id": user_session, "decision": "confirm"},
    )
    assert confirm_response.status_code == 200, confirm_response.text
    confirmed = confirm_response.json()
    assert confirmed["status"] == "completed"
    reservation_action_id = confirmed["reservation"]["action_id"]

    mine = client.get("/api/reservations/mine", headers={"X-Auth-Session": user_session})
    assert mine.status_code == 200
    assert [item["action_id"] for item in mine.json()["items"]] == [reservation_action_id]
    assert mine.json()["items"][0]["status"] == "pending"

    # 3) 관리자가 승인하면 상태가 바뀌고, 대기 목록에서는 사라진다.
    pending_before = client.get(
        "/api/admin/reservations/pending", headers={"X-Auth-Session": admin_session}
    )
    assert reservation_action_id in {item["action_id"] for item in pending_before.json()["items"]}

    decide_response = client.post(
        f"/api/admin/reservations/{reservation_action_id}/decision",
        headers={"X-Auth-Session": admin_session},
        json={"decision": "approve"},
    )
    assert decide_response.status_code == 200, decide_response.text
    assert decide_response.json()["status"] == "approved"

    pending_after = client.get(
        "/api/admin/reservations/pending", headers={"X-Auth-Session": admin_session}
    )
    assert reservation_action_id not in {item["action_id"] for item in pending_after.json()["items"]}

    mine_after = client.get("/api/reservations/mine", headers={"X-Auth-Session": user_session})
    assert mine_after.json()["items"][0]["status"] == "approved"

    # 4) 같은 예약을 다시 승인/거절하려 하면 이미 처리된 요청으로 거절된다(이중 처리 방지).
    duplicate_decision = client.post(
        f"/api/admin/reservations/{reservation_action_id}/decision",
        headers={"X-Auth-Session": admin_session},
        json={"decision": "reject"},
    )
    assert duplicate_decision.status_code == 409


def test_reservation_survives_new_repository_instance(client: TestClient) -> None:
    """행이 실제 Postgres에 있는지 확인 — 새 Repository 인스턴스로 다시 조회해도 보여야 한다."""
    from backend.app.repositories.reservation_repository import PostgresReservationRepository

    user_session = _login(client, "TEST", "1234")
    create_response = client.post(
        "/api/reservations",
        headers={"X-Auth-Session": user_session},
        json={"program": "먹이 주기 체험", "visit_time": "11:00", "headcount": 1},
    )
    action_id = create_response.json()["pending_action"]["action_id"]
    client.post(
        "/api/agent/confirm",
        headers={"X-Auth-Session": user_session},
        json={"action_id": action_id, "session_id": user_session, "decision": "confirm"},
    )

    fresh_repo = PostgresReservationRepository()
    stored = fresh_repo.list_for_user("TEST")
    assert any(item["program"] == "먹이 주기 체험" for item in stored)
