"""서버 발급 게스트 세션 저장소 (최두나 소유, 작업지시서 v1.1 5장/11.3절).

- 세션 ID는 추측하기 어려운 토큰으로 서버가 발급한다. 프론트가 임의로 정하지 않는다.
- In-Memory dict. 프로세스 재시작 시 전부 소멸한다 (P0 명시된 한계).
- TTL(SESSION_TTL_SECONDS, 기본 2시간) 경과 시 조회에서 무효로 처리하고,
  연결된 Trace도 함께 제거한다 (trace_repository.clear_session).
- 세션 ID 자체는 접근 비밀값으로 취급한다 — 로그·보고서에 원문을 남기지 않는다.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock

from backend.app.core.config import try_get_settings
from backend.app.core.redis_client import get_redis_client
from backend.app.repositories import trace_repository

_DEFAULT_TTL_SECONDS = 7200


@dataclass
class _SessionRecord:
    session_id: str
    created_at: datetime
    expires_at: datetime


_sessions: dict[str, _SessionRecord] = {}
_lock = Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ttl_seconds() -> int:
    settings = try_get_settings()
    if settings is not None:
        return settings.SESSION_TTL_SECONDS
    return _DEFAULT_TTL_SECONDS


def _create_session_memory(*, now: datetime | None = None) -> str:
    """추측 어려운 새 게스트 세션 ID를 발급하고 등록한다 (STORAGE_MODE=memory)."""
    current = now or _now()
    session_id = f"guest-{secrets.token_urlsafe(16)}"
    record = _SessionRecord(
        session_id=session_id,
        created_at=current,
        expires_at=current + timedelta(seconds=_ttl_seconds()),
    )
    with _lock:
        _sessions[session_id] = record
    return session_id


def _validate_session_memory(session_id: str, *, now: datetime | None = None) -> bool:
    """등록되고 만료되지 않은 세션인지 확인한다 (STORAGE_MODE=memory).

    위조/미등록 세션은 즉시 False. 만료된 세션은 False를 반환하며 저장소와
    연결된 Trace를 함께 제거한다(재조회 시 다시 만료 처리를 반복하지 않도록).
    """
    if not session_id:
        return False

    current = now or _now()
    with _lock:
        record = _sessions.get(session_id)
        if record is None:
            return False
        if record.expires_at <= current:
            del _sessions[session_id]
            expired = True
        else:
            expired = False

    if expired:
        trace_repository.clear_session(session_id)
        return False
    return True


def _use_redis() -> bool:
    settings = try_get_settings()
    return settings is not None and settings.STORAGE_MODE == "persistent"


def _create_session_redis() -> str:
    session_id = f"guest-{secrets.token_urlsafe(16)}"
    client = get_redis_client()
    client.set(f"session:{session_id}", "1", ex=_ttl_seconds())
    return session_id


def _validate_session_redis(session_id: str) -> bool:
    if not session_id:
        return False
    client = get_redis_client()
    exists = client.exists(f"session:{session_id}") == 1
    if not exists:
        return False
    client.expire(f"session:{session_id}", _ttl_seconds())
    return True


def create_session(*, now: datetime | None = None) -> str:
    """추측 어려운 새 게스트 세션 ID를 발급하고 등록한다."""
    if _use_redis():
        return _create_session_redis()
    return _create_session_memory(now=now)


def validate_session(session_id: str, *, now: datetime | None = None) -> bool:
    """등록되고 만료되지 않은 세션인지 확인한다."""
    if _use_redis():
        return _validate_session_redis(session_id)
    return _validate_session_memory(session_id, now=now)


def _reset_for_tests() -> None:
    """테스트 전용: 모듈 전역 상태를 초기화한다."""
    with _lock:
        _sessions.clear()
    if _use_redis():
        client = get_redis_client()
        for key in client.scan_iter("session:guest-*"):
            client.delete(key)
