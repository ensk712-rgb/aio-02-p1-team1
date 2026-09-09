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


class PostgresReservationRepository:
    """관리자 승인용 예약 요청 저장소의 Postgres 구현 (RESERVATION_STORAGE_MODE=persistent).

    ReservationRepository와 동일한 메서드 시그니처를 가진다 — main.py가 설정값에
    따라 둘 중 하나를 골라 주입한다.
    """

    def create(self, *, user_id: str, program: str, visit_time: str, headcount: int) -> dict[str, Any]:
        from psycopg.rows import dict_row

        from backend.app.core.db import get_connection_pool

        action_id = f"action_{uuid4().hex}"
        created_at = datetime.now(timezone.utc)
        pool = get_connection_pool()
        with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO reservations
                    (action_id, user_id, program, visit_time, headcount, status, created_at, decided_at)
                VALUES (%s, %s, %s, %s, %s, 'pending', %s, NULL)
                RETURNING action_id, user_id, program, visit_time, headcount, status, created_at, decided_at
                """,
                (action_id, user_id, program, visit_time, headcount, created_at),
            )
            row = cur.fetchone()
            conn.commit()
        return self._serialize(row)

    def list_pending(self) -> list[dict[str, Any]]:
        return self._list_where("status = 'pending'", ())

    def list_for_user(self, user_id: str) -> list[dict[str, Any]]:
        return self._list_where("user_id = %s", (user_id,))

    def decide(self, action_id: str, decision: Decision) -> dict[str, Any] | None:
        from psycopg.rows import dict_row

        from backend.app.core.db import get_connection_pool

        new_status = "approved" if decision == "approve" else "rejected"
        decided_at = datetime.now(timezone.utc)
        pool = get_connection_pool()
        with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            # 행 잠금 후 조건부 UPDATE로, 동시에 두 번 결정이 들어와도 한 번만 반영된다.
            cur.execute("SELECT action_id FROM reservations WHERE action_id = %s FOR UPDATE", (action_id,))
            if cur.fetchone() is None:
                conn.commit()
                return None

            cur.execute(
                """
                UPDATE reservations
                SET status = %s, decided_at = %s
                WHERE action_id = %s AND status = 'pending'
                RETURNING action_id, user_id, program, visit_time, headcount, status, created_at, decided_at
                """,
                (new_status, decided_at, action_id),
            )
            row = cur.fetchone()
            conn.commit()
        return self._serialize(row) if row else None

    def _list_where(self, condition: str, params: tuple) -> list[dict[str, Any]]:
        from psycopg.rows import dict_row

        from backend.app.core.db import get_connection_pool

        pool = get_connection_pool()
        with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT action_id, user_id, program, visit_time, headcount, status, created_at, decided_at "
                f"FROM reservations WHERE {condition}",
                params,
            )
            rows = cur.fetchall()
        return [self._serialize(row) for row in rows]

    @staticmethod
    def _serialize(row: dict[str, Any]) -> dict[str, Any]:
        return {
            **row,
            "created_at": row["created_at"].isoformat(),
            "decided_at": row["decided_at"].isoformat() if row["decided_at"] else None,
        }
