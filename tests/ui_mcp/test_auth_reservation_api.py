"""DB 로그인과 예약 승인 API의 최소 정책 시험."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.main import create_app
from backend.app.repositories.auth_session_repository import AuthSessionRepository
from backend.app.repositories.reservation_repository import ReservationRepository
from backend.app.repositories.pending_action_repository import PendingActionRepository
from backend.app.repositories.user_repository import UserRepository


def _client(tmp_path, *, pending_actions=None) -> tuple[TestClient, UserRepository]:
    users = UserRepository(tmp_path / "auth.db")
    app = create_app(
        Settings(_env_file=None, APP_MODE="mock"),
        user_repository=users,
        auth_sessions=AuthSessionRepository(),
        reservations=ReservationRepository(),
        pending_actions=pending_actions,
    )
    return TestClient(app), users


def test_database_contains_fixed_user_and_admin(tmp_path) -> None:
    client, users = _client(tmp_path)
    del client
    with sqlite3.connect(users._db_path) as connection:
        rows = connection.execute(
            "SELECT user_id, role FROM users ORDER BY user_id"
        ).fetchall()
    assert rows == [("TEST", "user"), ("admin", "admin")]


def test_login_rejects_wrong_password_without_echo(tmp_path) -> None:
    client, _ = _client(tmp_path)
    response = client.post(
        "/api/auth/login",
        json={"user_id": "TEST", "password": "wrong-secret"},
    )
    assert response.status_code == 401
    assert "wrong-secret" not in response.text
    assert "1234" not in response.text


def test_auth_session_can_restore_login_until_logout(tmp_path) -> None:
    client, _ = _client(tmp_path)
    login = client.post(
        "/api/auth/login", json={"user_id": "TEST", "password": "1234"}
    ).json()
    headers = {"X-Auth-Session": login["auth_session_id"]}

    restored = client.get("/api/auth/session", headers=headers)
    assert restored.status_code == 200
    assert restored.json() == {"success": True, "user_id": "TEST", "role": "user"}

    assert client.post("/api/auth/logout", headers=headers).status_code == 204
    assert client.get("/api/auth/session", headers=headers).status_code == 401


def test_login_reservation_and_admin_approval_flow(tmp_path) -> None:
    client, _ = _client(tmp_path)
    login = client.post(
        "/api/auth/login", json={"user_id": "TEST", "password": "1234"}
    )
    assert login.status_code == 200
    body = login.json()
    assert body["success"] is True
    assert body["user_id"] == "TEST"
    assert body["role"] == "user"
    assert "password" not in body
    headers = {"X-Auth-Session": body["auth_session_id"]}

    assert client.get("/api/admin/reservations/pending").status_code == 401
    created = client.post(
        "/api/reservations",
        headers=headers,
        json={"program": "사육사 체험", "visit_time": "15:00", "headcount": 2},
    )
    assert created.status_code == 201
    assert created.json()["status"] == "confirmation_required"
    action = created.json()["pending_action"]
    action_id = action["action_id"]
    assert action["approval_status"] == "pending"

    # 사용자 확인 전에는 실제 예약과 관리자 승인 목록이 변경되지 않는다.
    assert client.get("/api/admin/reservations/pending", headers=headers).status_code == 403
    confirmed = client.post(
        "/api/agent/confirm",
        headers=headers,
        json={"action_id": action_id, "session_id": body["auth_session_id"], "decision": "confirm"},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "completed"
    reservation_id = confirmed.json()["reservation"]["action_id"]

    admin_login = client.post(
        "/api/auth/login", json={"user_id": "admin", "password": "1234"}
    ).json()
    assert admin_login["role"] == "admin"
    admin_headers = {"X-Auth-Session": admin_login["auth_session_id"]}
    pending = client.get("/api/admin/reservations/pending", headers=admin_headers)
    assert pending.status_code == 200
    assert [item["action_id"] for item in pending.json()["items"]] == [reservation_id]

    approved = client.post(
        f"/api/admin/reservations/{reservation_id}/decision",
        headers=admin_headers,
        json={"decision": "approve"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    duplicate = client.post(
        f"/api/admin/reservations/{reservation_id}/decision",
        headers=admin_headers,
        json={"decision": "approve"},
    )
    assert duplicate.status_code == 409
    mine = client.get("/api/reservations/mine", headers=headers)
    assert mine.json()["items"][0]["status"] == "approved"


def test_confirmation_cancel_expiry_session_and_reuse_are_server_decisions(tmp_path) -> None:
    current = [datetime(2026, 9, 7, 3, 0, tzinfo=timezone.utc)]
    pending = PendingActionRepository(ttl_seconds=120, now=lambda: current[0])
    client, _ = _client(tmp_path, pending_actions=pending)
    login = client.post("/api/auth/login", json={"user_id": "TEST", "password": "1234"}).json()
    headers = {"X-Auth-Session": login["auth_session_id"]}

    def propose() -> str:
        response = client.post(
            "/api/reservations",
            headers=headers,
            json={"program": "먹이주기 체험", "visit_time": "11:00", "headcount": 1},
        )
        return response.json()["pending_action"]["action_id"]

    cancelled_id = propose()
    cancelled = client.post(
        "/api/agent/confirm",
        headers=headers,
        json={"action_id": cancelled_id, "session_id": login["auth_session_id"], "decision": "cancel"},
    )
    assert cancelled.json()["status"] == "rejected"
    reused = client.post(
        "/api/agent/confirm",
        headers=headers,
        json={"action_id": cancelled_id, "session_id": login["auth_session_id"], "decision": "confirm"},
    )
    assert reused.status_code == 409
    assert "이미 처리" in reused.json()["detail"]

    foreign_id = propose()
    mismatch = client.post(
        "/api/agent/confirm",
        headers=headers,
        json={"action_id": foreign_id, "session_id": "auth_forged", "decision": "confirm"},
    )
    assert mismatch.status_code == 403

    expired_id = propose()
    current[0] += timedelta(seconds=121)
    expired = client.post(
        "/api/agent/confirm",
        headers=headers,
        json={"action_id": expired_id, "session_id": login["auth_session_id"], "decision": "confirm"},
    )
    assert expired.status_code == 409
    assert "만료" in expired.json()["detail"]
    assert client.get("/api/admin/reservations/pending", headers=headers).status_code == 403
