"""session_memory_repository의 메모리/Redis 두 경로를 검증한다."""

from __future__ import annotations

import pytest

from backend.app.core.config import Settings
from backend.app.repositories import session_memory_repository as repo


@pytest.fixture(autouse=True)
def _reset():
    repo._reset_for_tests()
    yield
    repo._reset_for_tests()


def test_memory_mode_keeps_last_n_turns_in_order() -> None:
    repo.append_message("session_1", "user", "안녕")
    repo.append_message("session_1", "agent", "안녕하세요")
    repo.append_message("session_1", "user", "호랑이 어디 있어?")

    history = repo.get_recent("session_1")
    assert [item["text"] for item in history] == ["안녕", "안녕하세요", "호랑이 어디 있어?"]
    assert history[0]["role"] == "user"


def test_memory_mode_trims_to_max_turns(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.app.core import config as config_module

    # try_get_settings 자체가 아니라 get_settings를 patch해야 한다 — try_get_settings는
    # 이미 다른 모듈이 이름으로 직접 import해 간 경우가 있어(예: session_memory_repository.py)
    # 그 바인딩에는 영향을 못 주지만, get_settings는 try_get_settings 내부에서 매번
    # config 모듈 전역을 통해 동적으로 조회되므로 patch가 모든 호출부에 반영된다.
    monkeypatch.setattr(
        config_module, "get_settings",
        lambda: Settings(_env_file=None, SESSION_MEMORY_MAX_TURNS=2),
    )
    for i in range(4):
        repo.append_message("session_2", "user", f"message-{i}")

    history = repo.get_recent("session_2")
    assert [item["text"] for item in history] == ["message-2", "message-3"]


@pytest.mark.integration
def test_redis_mode_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.app.core import config as config_module
    from backend.app.core import redis_client as redis_client_module

    redis_client_module._reset_client_for_tests()
    test_settings = Settings(
        _env_file=None,
        STORAGE_MODE="persistent",
        REDIS_URL="redis://127.0.0.1:6380/0",
    )
    monkeypatch.setattr(config_module, "get_settings", lambda: test_settings)
    client = redis_client_module.get_redis_client(url=test_settings.REDIS_URL)
    client.delete("session_memory:redis_test")

    repo.append_message("redis_test", "user", "레디스 테스트")
    history = repo.get_recent("redis_test")

    assert history == [{"role": "user", "text": "레디스 테스트"}]
    client.delete("session_memory:redis_test")
