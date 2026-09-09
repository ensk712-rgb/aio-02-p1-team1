"""P1 변경 작업을 120초 동안 보관하고 원자적으로 소비하는 저장소."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any, Literal
from uuid import uuid4


PendingDecision = Literal["confirm", "cancel"]


class PendingActionRepository:
    def __init__(
        self,
        *,
        ttl_seconds: int = 120,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._ttl_seconds = ttl_seconds
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._items: dict[str, dict[str, Any]] = {}
        self._lock = Lock()

    def create(
        self,
        *,
        session_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        summary: str,
    ) -> dict[str, Any]:
        created_at = self._now()
        item = {
            "action_id": f"action_{uuid4().hex}",
            "session_id": session_id,
            "tool_name": tool_name,
            "arguments": dict(arguments),
            "summary": summary,
            "approval_status": "pending",
            "created_at": created_at.isoformat(),
            "expires_at": (created_at + timedelta(seconds=self._ttl_seconds)).isoformat(),
            "decided_at": None,
        }
        with self._lock:
            self._items[item["action_id"]] = item
        return self._public(item)

    def decide(
        self,
        action_id: str,
        *,
        session_id: str,
        decision: PendingDecision,
    ) -> tuple[str, dict[str, Any] | None]:
        """상태 판정과 processing 전환을 한 lock 안에서 수행한다."""
        with self._lock:
            item = self._items.get(action_id)
            if item is None:
                return "not_found", None
            if item["session_id"] != session_id:
                return "session_mismatch", None
            if item["approval_status"] != "pending":
                return "already_processed", self._public(item)
            if self._now() >= datetime.fromisoformat(item["expires_at"]):
                item["approval_status"] = "expired"
                item["decided_at"] = self._now().isoformat()
                return "expired", self._public(item)

            item["approval_status"] = "processing" if decision == "confirm" else "cancelled"
            item["decided_at"] = self._now().isoformat()
            return "ready" if decision == "confirm" else "cancelled", self._public(item)

    def complete(self, action_id: str) -> dict[str, Any]:
        with self._lock:
            item = self._items[action_id]
            if item["approval_status"] != "processing":
                raise RuntimeError("processing 상태의 작업만 완료할 수 있습니다.")
            item["approval_status"] = "completed"
            return self._public(item)

    def get_pending_for_session(self, session_id: str) -> dict[str, Any] | None:
        """새로고침된 화면이 동일 로그인 세션의 미처리 요청을 복원한다."""
        with self._lock:
            pending = [
                item
                for item in self._items.values()
                if item["session_id"] == session_id
                and item["approval_status"] == "pending"
                and self._now() < datetime.fromisoformat(item["expires_at"])
            ]
            if not pending:
                return None
            return self._public(max(pending, key=lambda item: item["created_at"]))

    @staticmethod
    def _public(item: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value
            for key, value in item.items()
            if key != "session_id"
        }
