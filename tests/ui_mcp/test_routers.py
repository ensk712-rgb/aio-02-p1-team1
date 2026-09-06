from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers.admin_router import create_admin_router


def test_admin_trace_requires_configured_token(monkeypatch) -> None:
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    app = FastAPI()
    app.include_router(create_admin_router(lambda _: []))
    assert TestClient(app).get("/api/admin/trace?session_id=s1").status_code == 401


def test_admin_trace_returns_only_requested_session(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_TOKEN", "test-admin")
    seen = []
    app = FastAPI()
    app.include_router(create_admin_router(lambda session_id: seen.append(session_id) or [{"run_id": "r1", "status": "completed", "trace": []}]))
    response = TestClient(app).get("/api/admin/trace?session_id=s1", headers={"Authorization": "Bearer test-admin"})
    assert response.status_code == 200
    assert response.json()["runs"][0]["run_id"] == "r1"
    assert seen == ["s1"]
