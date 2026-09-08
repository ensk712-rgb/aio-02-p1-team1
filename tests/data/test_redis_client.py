"""Redis 연결 헬퍼를 검증한다 (실제 Redis 필요)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_get_redis_client_can_ping_and_roundtrip_a_value() -> None:
    from backend.app.core.redis_client import get_redis_client

    client = get_redis_client(url="redis://127.0.0.1:6380/0")
    assert client.ping() is True

    client.set("zoo:test:ping", "pong", ex=5)
    assert client.get("zoo:test:ping") == "pong"
    client.delete("zoo:test:ping")
