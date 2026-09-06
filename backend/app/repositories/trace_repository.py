"""세션별 실행 Trace 저장소 (최두나 소유, 작업지시서 v1.1 5장/8.3절).

- In-Memory. 세션당 최근 20개 실행만 유지한다(오래된 것부터 자동 제거).
- 저장소 접근만 담당하며 업무 판단(상태 계산 등)은 하지 않는다.
- 세션이 만료되면 session_repository가 이 모듈의 clear_session()을 호출해
  연결된 Trace를 함께 제거한다.
"""

from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
from typing import Any

_MAX_RUNS_PER_SESSION = 20

_runs: dict[str, deque[dict[str, Any]]] = defaultdict(
    lambda: deque(maxlen=_MAX_RUNS_PER_SESSION)
)
_lock = Lock()


def save_run(
    session_id: str, run_id: str, status: str, trace: list[dict[str, Any]]
) -> None:
    """세션의 실행 기록에 한 run을 추가한다. 21번째부터는 가장 오래된 것이 밀려난다."""
    entry = {"run_id": run_id, "status": status, "trace": trace}
    with _lock:
        _runs[session_id].append(entry)


def list_runs(session_id: str) -> list[dict[str, Any]]:
    """세션의 실행 기록을 저장된 순서(오래된 것 -> 최신) 그대로 반환한다."""
    with _lock:
        return list(_runs.get(session_id, ()))


def clear_session(session_id: str) -> None:
    """세션 만료/삭제 시 연결된 Trace를 전부 제거한다."""
    with _lock:
        _runs.pop(session_id, None)


def _reset_for_tests() -> None:
    """테스트 전용: 모듈 전역 상태를 초기화한다."""
    with _lock:
        _runs.clear()
