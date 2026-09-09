"""예약/확인대기 영구 저장 테이블 스키마를 검증한다 (실제 DB 필요)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_ensure_reservation_schema_creates_tables() -> None:
    from backend.app.core.db import ensure_reservation_schema, get_connection_pool

    pool = get_connection_pool(dsn="postgresql://zoo:zoo@127.0.0.1:5432/zoo")
    ensure_reservation_schema(pool)

    with pool.connection() as conn:
        for table_name in ("reservations", "pending_reservation_actions"):
            row = conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_name = %s",
                (table_name,),
            ).fetchone()
            assert row is not None, f"{table_name} 테이블이 생성되지 않았습니다."

        columns = {
            row[0]
            for row in conn.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'pending_reservation_actions'"
            ).fetchall()
        }
        assert {
            "action_id", "session_id", "tool_name", "arguments", "summary",
            "approval_status", "created_at", "expires_at", "decided_at",
        }.issubset(columns)
