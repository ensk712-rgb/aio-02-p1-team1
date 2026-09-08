"""Redis 클라이언트 지연 초기화 헬퍼."""

from __future__ import annotations

import redis

from backend.app.core.config import try_get_settings

_client: redis.Redis | None = None


def _resolve_url(url: str | None) -> str:
    if url:
        return url
    settings = try_get_settings()
    if settings is None or not settings.REDIS_URL:
        raise RuntimeError("REDIS_URL이 설정되지 않았습니다.")
    return settings.REDIS_URL


def get_redis_client(url: str | None = None) -> redis.Redis:
    """프로세스 전체에서 재사용하는 단일 Redis 클라이언트를 반환한다.

    decode_responses=True로 항상 str을 주고받는다 (bytes 처리 분기를 없앤다).
    """
    global _client
    if _client is None:
        _client = redis.Redis.from_url(_resolve_url(url), decode_responses=True)
    return _client


def check_redis() -> bool:
    """Redis 연결이 살아있는지 가볍게 확인한다."""
    try:
        return get_redis_client().ping() is True
    except Exception:
        return False


def _reset_client_for_tests() -> None:
    """테스트 전용: 캐시된 클라이언트를 초기화한다."""
    global _client
    _client = None
