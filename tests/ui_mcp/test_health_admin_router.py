"""health와 관리자 Trace Router 계약 시험."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.main import create_app
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


def test_cors_uses_configured_origin_allowlist() -> None:
    app = create_app(
        Settings(
            _env_file=None,
            APP_MODE="mock",
            CORS_ALLOW_ORIGINS="http://localhost:8501,http://192.100.200.198:8501",
        )
    )
    client = TestClient(app)
    allowed = client.options(
        "/api/agent/ask",
        headers={
            "Origin": "http://localhost:8501",
            "Access-Control-Request-Method": "POST",
        },
    )
    blocked = client.options(
        "/api/agent/ask",
        headers={
            "Origin": "http://untrusted.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:8501"
    assert "access-control-allow-origin" not in blocked.headers


def _admin_client(token: str) -> TestClient:
    app = FastAPI()
    app.include_router(
        create_admin_router(
            lambda session_id: [
                {"run_id": "run_1", "status": "completed", "trace": []}
            ] if session_id == "session_1" else [],
            admin_token=token,
            list_recent_summaries=lambda: [
                {
                    "session_id": "session_1",
                    "last_run_at": "2026-09-09T00:00:00+00:00",
                    "status": "completed",
                    "question_preview": "먹이시간 알려줘",
                    "tools": ["get_feeding_schedule"],
                }
            ],
            get_summary=lambda session_id: {"session_id": session_id} if session_id == "session_1" else None,
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


class FakePersistenceCheck:
    def __init__(self, postgres_ok: bool, redis_ok: bool) -> None:
        self.postgres_ok = postgres_ok
        self.redis_ok = redis_ok

    def check_postgres(self) -> bool:
        return self.postgres_ok

    def check_redis(self) -> bool:
        return self.redis_ok


def test_health_reports_persistent_storage_status() -> None:
    app = FastAPI()
    app.include_router(
        create_health_router(
            FakeMcpHealth(True),
            app_mode="mock",
            storage="persistent",
            persistence_check=FakePersistenceCheck(True, True),
        )
    )
    response = TestClient(app).get("/api/health")
    assert response.status_code == 200
    assert response.json()["storage"] == "persistent"
    assert response.json()["postgres"] == "ok"
    assert response.json()["redis"] == "ok"


def test_admin_trace_returns_repository_contract() -> None:
    response = _admin_client("test-admin-token").get(
        "/api/admin/trace?session_id=session_1",
        headers={"Authorization": "Bearer test-admin-token"},
    )
    assert response.status_code == 200
    assert response.json()["runs"] == [{"run_id": "run_1", "status": "completed", "trace": []}]
    assert response.json()["detail_expired"] is False
    assert response.json()["summary"] == {"session_id": "session_1"}


def test_admin_recent_trace_sessions_requires_admin_and_returns_summaries() -> None:
    client = _admin_client("test-admin-token")
    assert client.get("/api/admin/trace/sessions").status_code == 401
    response = client.get(
        "/api/admin/trace/sessions",
        headers={"Authorization": "Bearer test-admin-token"},
    )
    assert response.status_code == 200
    assert response.json()["sessions"][0]["question_preview"] == "먹이시간 알려줘"
