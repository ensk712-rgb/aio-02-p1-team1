"""세션 대화 기억 저장소 (plan.md Phase 7 선반영).

- STORAGE_MODE=memory: In-Memory dict (프로세스 재시작 시 소멸, 기본값)
- STORAGE_MODE=persistent: Redis List, TTL=SESSION_TTL_SECONDS
- 두 모드 모두 SESSION_MEMORY_MAX_TURNS개까지만 최신 순으로 유지한다.
"""

from __future__ import annotations

import json
from collections import deque
from threading import Lock
from typing import TypedDict

from backend.app.core.config import try_get_settings
from backend.app.core.redis_client import get_redis_client

_DEFAULT_MAX_TURNS = 6
_DEFAULT_TTL_SECONDS = 7200


class _MessageEntry(TypedDict):
    role: str
    text: str


_messages: dict[str, deque[_MessageEntry]] = {}
_lock = Lock()


def _max_turns() -> int:
    settings = try_get_settings()
    return settings.SESSION_MEMORY_MAX_TURNS if settings is not None else _DEFAULT_MAX_TURNS


def _ttl_seconds() -> int:
    settings = try_get_settings()
    return settings.SESSION_TTL_SECONDS if settings is not None else _DEFAULT_TTL_SECONDS


def _use_redis() -> bool:
    settings = try_get_settings()
    return settings is not None and settings.STORAGE_MODE == "persistent"


def _append_memory(session_id: str, role: str, text: str) -> None:
    with _lock:
        if session_id not in _messages or _messages[session_id].maxlen != _max_turns():
            _messages[session_id] = deque(_messages.get(session_id, ()), maxlen=_max_turns())
        _messages[session_id].append({"role": role, "text": text})


def _get_recent_memory(session_id: str) -> list[_MessageEntry]:
    with _lock:
        return list(_messages.get(session_id, ()))


def _append_redis(session_id: str, role: str, text: str) -> None:
    client = get_redis_client()
    key = f"session_memory:{session_id}"
    client.rpush(key, json.dumps({"role": role, "text": text}, ensure_ascii=False))
    client.ltrim(key, -_max_turns(), -1)
    client.expire(key, _ttl_seconds())


def _get_recent_redis(session_id: str) -> list[_MessageEntry]:
    client = get_redis_client()
    raw_entries = client.lrange(f"session_memory:{session_id}", 0, -1)
    return [json.loads(entry) for entry in raw_entries]


def append_message(session_id: str, role: str, text: str) -> None:
    """세션에 메시지 한 건을 추가하고, 오래된 것부터 max_turns개까지만 유지한다."""
    if _use_redis():
        _append_redis(session_id, role, text)
    else:
        _append_memory(session_id, role, text)


def get_recent(session_id: str) -> list[_MessageEntry]:
    """저장된 순서(오래된 것 -> 최신) 그대로 최근 메시지를 반환한다."""
    if _use_redis():
        return _get_recent_redis(session_id)
    return _get_recent_memory(session_id)


def _reset_for_tests() -> None:
    """테스트 전용: 메모리 상태를 초기화한다 (Redis 키는 각 테스트가 직접 정리)."""
    with _lock:
        _messages.clear()
