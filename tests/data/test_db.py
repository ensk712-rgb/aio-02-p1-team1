"""Postgres 연결 풀과 pgvector 스키마 준비를 검증한다 (실제 DB 필요)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_ensure_schema_creates_pgvector_extension_and_table() -> None:
    from backend.app.core.db import ensure_schema, get_connection_pool

    pool = get_connection_pool(dsn="postgresql://zoo:zoo@127.0.0.1:5432/zoo")
    ensure_schema(pool)

    with pool.connection() as conn:
        row = conn.execute(
            "SELECT extname FROM pg_extension WHERE extname = 'vector'"
        ).fetchone()
        assert row is not None

        row = conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'document_chunks' AND column_name = 'embedding'"
        ).fetchone()
        assert row is not None
