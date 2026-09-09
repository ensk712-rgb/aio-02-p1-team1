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

    @staticmethod
    def _public(item: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value
            for key, value in item.items()
            if key != "session_id"
        }


class PostgresPendingActionRepository:
    """P1 변경 작업 확인대기 저장소의 Postgres 구현 (RESERVATION_STORAGE_MODE=persistent).

    PendingActionRepository와 동일한 메서드 시그니처를 가진다.
    """

    def __init__(
        self,
        *,
        ttl_seconds: int = 120,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._ttl_seconds = ttl_seconds
        self._now = now or (lambda: datetime.now(timezone.utc))

    def create(
        self,
        *,
        session_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        summary: str,
    ) -> dict[str, Any]:
        from psycopg.rows import dict_row
        from psycopg.types.json import Jsonb

        from backend.app.core.db import get_connection_pool

        action_id = f"action_{uuid4().hex}"
        created_at = self._now()
        expires_at = created_at + timedelta(seconds=self._ttl_seconds)
        pool = get_connection_pool()
        with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO pending_reservation_actions
                    (action_id, session_id, tool_name, arguments, summary,
                     approval_status, created_at, expires_at, decided_at)
                VALUES (%s, %s, %s, %s, %s, 'pending', %s, %s, NULL)
                RETURNING action_id, session_id, tool_name, arguments, summary,
                          approval_status, created_at, expires_at, decided_at
                """,
                (action_id, session_id, tool_name, Jsonb(dict(arguments)), summary, created_at, expires_at),
            )
            row = cur.fetchone()
            conn.commit()
        return self._public(self._serialize(row))

    def decide(
        self,
        action_id: str,
        *,
        session_id: str,
        decision: PendingDecision,
    ) -> tuple[str, dict[str, Any] | None]:
        from psycopg.rows import dict_row

        from backend.app.core.db import get_connection_pool

        pool = get_connection_pool()
        with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT action_id, session_id, tool_name, arguments, summary,
                       approval_status, created_at, expires_at, decided_at
                FROM pending_reservation_actions WHERE action_id = %s FOR UPDATE
                """,
                (action_id,),
            )
            row = cur.fetchone()
            if row is None:
                conn.commit()
                return "not_found", None

            item = self._serialize(row)
            if item["session_id"] != session_id:
                conn.commit()
                return "session_mismatch", None
            if item["approval_status"] != "pending":
                conn.commit()
                return "already_processed", self._public(item)

            now = self._now()
            if now >= datetime.fromisoformat(item["expires_at"]):
                cur.execute(
                    """
                    UPDATE pending_reservation_actions
                    SET approval_status = 'expired', decided_at = %s
                    WHERE action_id = %s
                    RETURNING action_id, session_id, tool_name, arguments, summary,
                              approval_status, created_at, expires_at, decided_at
                    """,
                    (now, action_id),
                )
                updated = self._serialize(cur.fetchone())
                conn.commit()
                return "expired", self._public(updated)

            new_status = "processing" if decision == "confirm" else "cancelled"
            cur.execute(
                """
                UPDATE pending_reservation_actions
                SET approval_status = %s, decided_at = %s
                WHERE action_id = %s
                RETURNING action_id, session_id, tool_name, arguments, summary,
                          approval_status, created_at, expires_at, decided_at
                """,
                (new_status, now, action_id),
            )
            updated = self._serialize(cur.fetchone())
            conn.commit()
            outcome = "ready" if decision == "confirm" else "cancelled"
            return outcome, self._public(updated)

    def complete(self, action_id: str) -> dict[str, Any]:
        from psycopg.rows import dict_row

        from backend.app.core.db import get_connection_pool

        pool = get_connection_pool()
        with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                UPDATE pending_reservation_actions
                SET approval_status = 'completed'
                WHERE action_id = %s AND approval_status = 'processing'
                RETURNING action_id, session_id, tool_name, arguments, summary,
                          approval_status, created_at, expires_at, decided_at
                """,
                (action_id,),
            )
            row = cur.fetchone()
            conn.commit()
        if row is None:
            raise RuntimeError("processing 상태의 작업만 완료할 수 있습니다.")
        return self._public(self._serialize(row))

    @staticmethod
    def _serialize(row: dict[str, Any]) -> dict[str, Any]:
        return {
            **row,
            "arguments": dict(row["arguments"]),
            "created_at": row["created_at"].isoformat(),
            "expires_at": row["expires_at"].isoformat(),
            "decided_at": row["decided_at"].isoformat() if row["decided_at"] else None,
        }

    @staticmethod
    def _public(item: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in item.items() if key != "session_id"}
