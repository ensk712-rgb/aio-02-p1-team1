"""health와 관리자 Trace Router 계약 시험."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers.admin_router import create_admin_router
from backend.app.routers.health_router import create_health_router


class FakeMcpHealth:
    def __init__(self, available: bool) -> None:
        self.available = available

    async def check_health(self) -> bool:
        return self.available


def _health_client(available: bool) -> TestClient:
    app = FastAPI()
    app.include_router(
        create_health_router(FakeMcpHealth(available), app_mode="mock")
    )
    return TestClient(app)


def test_health_reports_actual_mcp_state() -> None:
    healthy = _health_client(True).get("/api/health")
    assert healthy.status_code == 200
    assert healthy.json() == {
        "status": "ok",
        "backend": "ok",
        "mcp": "ok",
        "storage": "memory",
        "app_mode": "mock",
    }

    degraded = _health_client(False).get("/api/health")
    assert degraded.status_code == 503
    assert degraded.json()["mcp"] == "unavailable"
    assert degraded.json()["status"] == "degraded"


def _admin_client(token: str) -> TestClient:
    app = FastAPI()
    app.include_router(
        create_admin_router(
            lambda session_id: [
                {"run_id": "run_1", "status": "completed", "trace": []}
            ] if session_id == "session_1" else [],
            admin_token=token,
        )
    )
    return TestClient(app)


def test_admin_trace_blocks_unconfigured_missing_and_wrong_token() -> None:
    assert _admin_client("").get("/api/admin/trace?session_id=session_1").status_code == 401

    client = _admin_client("test-admin-token")
    assert client.get("/api/admin/trace?session_id=session_1").status_code == 401
    wrong = client.get(
        "/api/admin/trace?session_id=session_1",
        headers={"Authorization": "Bearer wrong"},
    )
    assert wrong.status_code == 401
    assert "test-admin-token" not in wrong.text


def test_admin_trace_returns_repository_contract() -> None:
    response = _admin_client("test-admin-token").get(
        "/api/admin/trace?session_id=session_1",
        headers={"Authorization": "Bearer test-admin-token"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "runs": [{"run_id": "run_1", "status": "completed", "trace": []}]
    }
