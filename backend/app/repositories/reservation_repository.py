"""관리자 승인용 인메모리 예약 요청 저장소."""

from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock
from typing import Any, Literal
from uuid import uuid4


Decision = Literal["approve", "reject"]


class ReservationRepository:
    def __init__(self) -> None:
        self._items: dict[str, dict[str, Any]] = {}
        self._lock = Lock()

    def create(self, *, user_id: str, program: str, visit_time: str, headcount: int) -> dict[str, Any]:
        action_id = f"action_{uuid4().hex}"
        item = {
            "action_id": action_id,
            "user_id": user_id,
            "program": program,
            "visit_time": visit_time,
            "headcount": headcount,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "decided_at": None,
        }
        with self._lock:
            self._items[action_id] = item
        return dict(item)

    def list_pending(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(item) for item in self._items.values() if item["status"] == "pending"]

    def decide(self, action_id: str, decision: Decision) -> dict[str, Any] | None:
        with self._lock:
            item = self._items.get(action_id)
            if item is None or item["status"] != "pending":
                return None
            item["status"] = "approved" if decision == "approve" else "rejected"
            item["decided_at"] = datetime.now(timezone.utc).isoformat()
            return dict(item)

    def list_for_user(self, user_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(item) for item in self._items.values() if item["user_id"] == user_id]
