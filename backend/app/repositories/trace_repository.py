"""세션별 실행 Trace 저장소 (최두나 소유, 작업지시서 v1.1 5장/8.3절).

- In-Memory. 세션당 최근 20개 실행만 유지한다(오래된 것부터 자동 제거).
- 저장소 접근만 담당하며 업무 판단(상태 계산 등)은 하지 않는다.
- 세션이 만료되면 session_repository가 이 모듈의 clear_session()을 호출해
  연결된 Trace를 함께 제거한다.
"""

from __future__ import annotations

import json
from collections import defaultdict, deque
from threading import Lock
from typing import Any

from backend.app.core.config import try_get_settings
from backend.app.core.redis_client import get_redis_client

_MAX_RUNS_PER_SESSION = 20

_runs: dict[str, deque[dict[str, Any]]] = defaultdict(
    lambda: deque(maxlen=_MAX_RUNS_PER_SESSION)
)
_lock = Lock()


def _save_run_memory(
    session_id: str, run_id: str, status: str, trace: list[dict[str, Any]]
) -> None:
    """세션의 실행 기록에 한 run을 추가한다. 21번째부터는 가장 오래된 것이 밀려난다."""
    entry = {"run_id": run_id, "status": status, "trace": trace}
    with _lock:
        _runs[session_id].append(entry)


def _list_runs_memory(session_id: str) -> list[dict[str, Any]]:
    """세션의 실행 기록을 저장된 순서(오래된 것 -> 최신) 그대로 반환한다."""
    with _lock:
        return list(_runs.get(session_id, ()))


def _clear_session_memory(session_id: str) -> None:
    """세션 만료/삭제 시 연결된 Trace를 전부 제거한다."""
    with _lock:
        _runs.pop(session_id, None)


def _use_redis() -> bool:
    settings = try_get_settings()
    return settings is not None and settings.STORAGE_MODE == "persistent"


def _ttl_seconds() -> int:
    settings = try_get_settings()
    return settings.SESSION_TTL_SECONDS if settings is not None else 7200


def _save_run_redis(session_id: str, run_id: str, status: str, trace: list[dict]) -> None:
    entry = json.dumps({"run_id": run_id, "status": status, "trace": trace}, ensure_ascii=False)
    client = get_redis_client()
    key = f"trace:{session_id}"
    client.rpush(key, entry)
    client.ltrim(key, -_MAX_RUNS_PER_SESSION, -1)
    client.expire(key, _ttl_seconds())


def _list_runs_redis(session_id: str) -> list[dict]:
    client = get_redis_client()
    raw_entries = client.lrange(f"trace:{session_id}", 0, -1)
    return [json.loads(entry) for entry in raw_entries]


def _clear_session_redis(session_id: str) -> None:
    get_redis_client().delete(f"trace:{session_id}")


def save_run(session_id: str, run_id: str, status: str, trace: list[dict[str, Any]]) -> None:
    """세션의 실행 기록에 한 run을 추가한다."""
    if _use_redis():
        _save_run_redis(session_id, run_id, status, trace)
    else:
        _save_run_memory(session_id, run_id, status, trace)


def list_runs(session_id: str) -> list[dict[str, Any]]:
    """세션의 실행 기록을 저장된 순서 그대로 반환한다."""
    if _use_redis():
        return _list_runs_redis(session_id)
    return _list_runs_memory(session_id)


def clear_session(session_id: str) -> None:
    """세션 만료/삭제 시 연결된 Trace를 전부 제거한다."""
    if _use_redis():
        _clear_session_redis(session_id)
    else:
        _clear_session_memory(session_id)


def _reset_for_tests() -> None:
    """테스트 전용: 모듈 전역 상태를 초기화한다."""
    with _lock:
        _runs.clear()
