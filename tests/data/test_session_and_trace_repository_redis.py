"""STORAGE_MODE=persistent 경로의 session/trace 저장소를 실제 Redis로 검증한다."""

from __future__ import annotations

import time

import pytest

from backend.app.core.config import Settings

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _persistent_settings(monkeypatch: pytest.MonkeyPatch):
    from backend.app.core import config as config_module
    from backend.app.core import redis_client as redis_client_module

    redis_client_module._reset_client_for_tests()
    test_settings = Settings(
        _env_file=None,
        STORAGE_MODE="persistent",
        REDIS_URL="redis://127.0.0.1:6380/0",
        SESSION_TTL_SECONDS=1,
    )
    monkeypatch.setattr(config_module, "get_settings", lambda: test_settings)
    monkeypatch.setattr(config_module, "try_get_settings", lambda: test_settings)

    client = redis_client_module.get_redis_client(url=test_settings.REDIS_URL)
    yield client
    for key in client.scan_iter("session:test:*"):
        client.delete(key)
    for key in client.scan_iter("trace:test:*"):
        client.delete(key)


def test_redis_session_roundtrip_and_ttl_expiry(_persistent_settings) -> None:
    from backend.app.repositories import session_repository, trace_repository

    client = _persistent_settings
    session_id = session_repository.create_session()

    # 실제로 Redis 키가 생겼는지 직접 확인한다 (In-Memory dict만으로는 통과할 수 없는 검증).
    assert client.exists(f"session:{session_id}") == 1

    assert session_repository.validate_session(session_id) is True

    trace_repository.save_run(session_id, "run_1", "completed", [{"owner": "runtime"}])
    assert client.exists(f"trace:{session_id}") == 1
    assert trace_repository.list_runs(session_id) == [
        {"run_id": "run_1", "status": "completed", "trace": [{"owner": "runtime"}]}
    ]

    time.sleep(1.5)  # SESSION_TTL_SECONDS=1 초과 대기

    assert client.exists(f"session:{session_id}") == 0
    assert session_repository.validate_session(session_id) is False
    assert trace_repository.list_runs(session_id) == []
