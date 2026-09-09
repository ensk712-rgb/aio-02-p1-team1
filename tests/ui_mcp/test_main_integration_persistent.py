"""STORAGE_MODE=persistent로 main.py를 띄워 /api/health를 검증한다 (실제 Postgres/Redis 필요)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.core.db import ensure_schema, get_connection_pool

pytestmark = pytest.mark.integration


def test_health_ok_when_postgres_and_redis_reachable() -> None:
    from backend.app.main import create_app

    settings = Settings(
        _env_file=None,
        APP_MODE="mock",
        STORAGE_MODE="persistent",
        DATABASE_URL="postgresql://zoo:zoo@127.0.0.1:5432/zoo",
        REDIS_URL="redis://127.0.0.1:6380/0",
        MCP_SERVER_URL="http://192.100.200.199:8100/mcp",  # 이 테스트는 MCP는 검사하지 않음
    )
    ensure_schema(get_connection_pool(dsn=settings.DATABASE_URL))

    with TestClient(create_app(settings)) as client:
        response = client.get("/api/health")

    assert response.json()["storage"] == "persistent"
    assert response.json()["postgres"] == "ok"
    assert response.json()["redis"] == "ok"
