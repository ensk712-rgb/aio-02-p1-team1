"""PostgreSQL 기반 예약 및 예약 확인 대기 저장소."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from uuid import uuid4

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from backend.app.core.db import get_connection_pool


def _serialize(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value.isoformat() if isinstance(value, datetime) else value
        for key, value in row.items()
    }


class PostgresReservationRepository:
    def __init__(self, pool: ConnectionPool | None = None) -> None:
        self._pool = pool or get_connection_pool()

    def create(self, *, user_id: str, program: str, visit_time: str, headcount: int) -> dict[str, Any]:
        action_id = f"action_{uuid4().hex}"
        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                row = cursor.execute(
                    """
                    INSERT INTO reservations
                        (action_id, user_id, program, visit_time, headcount, status)
                    VALUES (%s, %s, %s, %s, %s, 'pending')
                    RETURNING *
                    """,
                    (action_id, user_id, program, visit_time, headcount),
                ).fetchone()
            conn.commit()
        assert row is not None
        return _serialize(dict(row))

    def list_pending(self) -> list[dict[str, Any]]:
        with self._pool.connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
            rows = cursor.execute(
                "SELECT * FROM reservations WHERE status = 'pending' ORDER BY created_at, action_id"
            ).fetchall()
        return [_serialize(dict(row)) for row in rows]

    def decide(self, action_id: str, decision: Literal["approve", "reject"]) -> dict[str, Any] | None:
        status = "approved" if decision == "approve" else "rejected"
        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                row = cursor.execute(
                    """
                    UPDATE reservations
                    SET status = %s, decided_at = now()
                    WHERE action_id = %s AND status = 'pending'
                    RETURNING *
                    """,
                    (status, action_id),
                ).fetchone()
            conn.commit()
        return _serialize(dict(row)) if row is not None else None

    def list_for_user(self, user_id: str) -> list[dict[str, Any]]:
        with self._pool.connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
            rows = cursor.execute(
                "SELECT * FROM reservations WHERE user_id = %s ORDER BY created_at, action_id",
                (user_id,),
            ).fetchall()
        return [_serialize(dict(row)) for row in rows]


class PostgresPendingActionRepository:
    def __init__(self, *, ttl_seconds: int = 120, pool: ConnectionPool | None = None) -> None:
        self._ttl_seconds = ttl_seconds
        self._pool = pool or get_connection_pool()

    def create(self, *, session_id: str, tool_name: str, arguments: dict[str, Any], summary: str) -> dict[str, Any]:
        action_id = f"action_{uuid4().hex}"
        created_at = datetime.now(timezone.utc)
        expires_at = created_at + timedelta(seconds=self._ttl_seconds)
        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                row = cursor.execute(
                    """
                    INSERT INTO pending_reservation_actions
                        (action_id, session_id, tool_name, arguments, summary,
                         approval_status, created_at, expires_at)
                    VALUES (%s, %s, %s, %s::jsonb, %s, 'pending', %s, %s)
                    RETURNING *
                    """,
                    (action_id, session_id, tool_name, json.dumps(arguments, ensure_ascii=False), summary, created_at, expires_at),
                ).fetchone()
            conn.commit()
        assert row is not None
        return self._public(dict(row))

    def decide(self, action_id: str, *, session_id: str, decision: Literal["confirm", "cancel"]):
        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                row = cursor.execute(
                    "SELECT * FROM pending_reservation_actions WHERE action_id = %s FOR UPDATE",
                    (action_id,),
                ).fetchone()
                if row is None:
                    conn.rollback()
                    return "not_found", None
                item = dict(row)
                if item["session_id"] != session_id:
                    conn.rollback()
                    return "session_mismatch", None
                if item["approval_status"] != "pending":
                    conn.rollback()
                    return "already_processed", self._public(item)
                now = datetime.now(timezone.utc)
                if now >= item["expires_at"]:
                    item = dict(cursor.execute(
                        "UPDATE pending_reservation_actions SET approval_status = 'expired', decided_at = %s WHERE action_id = %s RETURNING *",
                        (now, action_id),
                    ).fetchone())
                    conn.commit()
                    return "expired", self._public(item)
                next_status = "processing" if decision == "confirm" else "cancelled"
                item = dict(cursor.execute(
                    "UPDATE pending_reservation_actions SET approval_status = %s, decided_at = %s WHERE action_id = %s RETURNING *",
                    (next_status, now, action_id),
                ).fetchone())
            conn.commit()
        return ("ready" if decision == "confirm" else "cancelled"), self._public(item)

    def complete(self, action_id: str) -> dict[str, Any]:
        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                row = cursor.execute(
                    """
                    UPDATE pending_reservation_actions SET approval_status = 'completed'
                    WHERE action_id = %s AND approval_status = 'processing'
                    RETURNING *
                    """,
                    (action_id,),
                ).fetchone()
            conn.commit()
        if row is None:
            raise RuntimeError("processing 상태의 작업만 완료할 수 있습니다.")
        return self._public(dict(row))

    def get_pending_for_session(self, session_id: str) -> dict[str, Any] | None:
        with self._pool.connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
            row = cursor.execute(
                """
                SELECT * FROM pending_reservation_actions
                WHERE session_id = %s AND approval_status = 'pending' AND expires_at > now()
                ORDER BY created_at DESC LIMIT 1
                """,
                (session_id,),
            ).fetchone()
        return self._public(dict(row)) if row is not None else None

    @staticmethod
    def _public(item: dict[str, Any]) -> dict[str, Any]:
        item = _serialize(item)
        item.pop("session_id", None)
        return item
