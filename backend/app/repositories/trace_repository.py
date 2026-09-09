"""세션별 실행 Trace 저장소 (최두나 소유, 작업지시서 v1.1 5장/8.3절).

- In-Memory. 세션당 최근 20개 실행만 유지한다(오래된 것부터 자동 제거).
- 저장소 접근만 담당하며 업무 판단(상태 계산 등)은 하지 않는다.
- 세션이 만료되면 session_repository가 이 모듈의 clear_session()을 호출해
  연결된 Trace를 함께 제거한다.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any

from backend.app.core.config import try_get_settings
from backend.app.core.redis_client import get_redis_client

_MAX_RUNS_PER_SESSION = 20
_MAX_RECENT_SESSIONS = 50
_SUMMARY_TTL_SECONDS = 24 * 60 * 60

_runs: dict[str, deque[dict[str, Any]]] = defaultdict(
    lambda: deque(maxlen=_MAX_RUNS_PER_SESSION)
)
_lock = Lock()
_summaries: dict[str, dict[str, Any]] = {}


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


def _mask_question(question: str | None) -> str:
    """목록에 표시할 질문은 짧게 자르고 줄바꿈을 제거한다."""
    value = " ".join((question or "").split())
    if not value:
        return "질문 내용 없음"
    value = re.sub(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", "***", value)
    value = re.sub(r"(?:01[016789]-?\d{3,4}-?\d{4}|\d{2,3}-?\d{3,4}-?\d{4})", "***", value)
    return value[:30] + ("…" if len(value) > 30 else "")


def _tool_names(trace: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for item in trace:
        data = item.get("data") if isinstance(item, dict) else None
        tool = data.get("tool") if isinstance(data, dict) else None
        if isinstance(tool, str) and tool and tool not in names:
            names.append(tool)
    return names


def _save_summary_memory(
    session_id: str, status: str, trace: list[dict[str, Any]], question: str | None, now: datetime
) -> None:
    with _lock:
        _summaries[session_id] = {
            "session_id": session_id,
            "last_run_at": now.isoformat(),
            "status": status,
            "question_preview": _mask_question(question),
            "tools": _tool_names(trace),
            "expires_at": (now + timedelta(seconds=_SUMMARY_TTL_SECONDS)).isoformat(),
        }


def _list_recent_summaries_memory(now: datetime) -> list[dict[str, Any]]:
    with _lock:
        expired = [
            session_id
            for session_id, summary in _summaries.items()
            if datetime.fromisoformat(summary["expires_at"]) <= now
        ]
        for session_id in expired:
            _summaries.pop(session_id, None)
        return sorted(
            (dict(summary) for summary in _summaries.values()),
            key=lambda summary: summary["last_run_at"],
            reverse=True,
        )[:_MAX_RECENT_SESSIONS]


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


def _save_summary_redis(
    session_id: str, status: str, trace: list[dict[str, Any]], question: str | None, now: datetime
) -> None:
    client = get_redis_client()
    summary = {
        "session_id": session_id,
        "last_run_at": now.isoformat(),
        "status": status,
        "question_preview": _mask_question(question),
        "tools": _tool_names(trace),
    }
    pipeline = client.pipeline()
    pipeline.setex(f"trace_summary:{session_id}", _SUMMARY_TTL_SECONDS, json.dumps(summary, ensure_ascii=False))
    pipeline.zadd("trace_summaries", {session_id: now.timestamp()})
    pipeline.zremrangebyscore("trace_summaries", "-inf", (now - timedelta(seconds=_SUMMARY_TTL_SECONDS)).timestamp())
    pipeline.execute()


def _list_recent_summaries_redis(now: datetime) -> list[dict[str, Any]]:
    client = get_redis_client()
    client.zremrangebyscore("trace_summaries", "-inf", (now - timedelta(seconds=_SUMMARY_TTL_SECONDS)).timestamp())
    session_ids = client.zrevrange("trace_summaries", 0, _MAX_RECENT_SESSIONS - 1)
    summaries: list[dict[str, Any]] = []
    for session_id in session_ids:
        raw = client.get(f"trace_summary:{session_id}")
        if raw is None:
            client.zrem("trace_summaries", session_id)
            continue
        summaries.append(json.loads(raw))
    return summaries


def save_run(
    session_id: str,
    run_id: str,
    status: str,
    trace: list[dict[str, Any]],
    *,
    question: str | None = None,
    now: datetime | None = None,
) -> None:
    """세션의 실행 기록에 한 run을 추가한다."""
    saved_at = now or datetime.now(timezone.utc)
    if _use_redis():
        _save_run_redis(session_id, run_id, status, trace)
        _save_summary_redis(session_id, status, trace, question, saved_at)
    else:
        _save_run_memory(session_id, run_id, status, trace)
        _save_summary_memory(session_id, status, trace, question, saved_at)


def list_runs(session_id: str) -> list[dict[str, Any]]:
    """세션의 실행 기록을 저장된 순서 그대로 반환한다."""
    if _use_redis():
        return _list_runs_redis(session_id)
    return _list_runs_memory(session_id)


def list_recent_summaries(*, now: datetime | None = None) -> list[dict[str, Any]]:
    """관리자 화면용 최근 24시간 세션 요약을 최신순으로 반환한다."""
    current = now or datetime.now(timezone.utc)
    if _use_redis():
        return _list_recent_summaries_redis(current)
    return _list_recent_summaries_memory(current)


def get_summary(session_id: str, *, now: datetime | None = None) -> dict[str, Any] | None:
    """상세 Trace 만료 여부 판단에 사용할 목록 요약을 반환한다."""
    return next(
        (summary for summary in list_recent_summaries(now=now) if summary["session_id"] == session_id),
        None,
    )


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
        _summaries.clear()
