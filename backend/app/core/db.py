"""Postgres(pgvector) 연결 풀과 스키마 준비를 담당한다.

- 커넥션은 프로세스당 하나의 Pool로 재사용한다 (요청마다 재연결하지 않는다).
- 여기서는 SQL 실행만 담당하고, 검색/삽입 업무 로직은 document_repository가 가진다.
"""

from __future__ import annotations

from psycopg_pool import ConnectionPool

from backend.app.core.config import try_get_settings

_pool: ConnectionPool | None = None

_SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS document_chunks (
    id BIGSERIAL PRIMARY KEY,
    doc_id TEXT NOT NULL,
    collection TEXT NOT NULL,
    title TEXT NOT NULL,
    page INTEGER,
    text TEXT NOT NULL,
    keywords TEXT[] NOT NULL DEFAULT '{}',
    embedding VECTOR(1536) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (doc_id, collection)
);

CREATE INDEX IF NOT EXISTS document_chunks_collection_idx
    ON document_chunks (collection);
"""


def _resolve_dsn(dsn: str | None) -> str:
    if dsn:
        return dsn
    settings = try_get_settings()
    if settings is None or not settings.DATABASE_URL:
        raise RuntimeError("DATABASE_URL이 설정되지 않았습니다.")
    return settings.DATABASE_URL


def get_connection_pool(dsn: str | None = None) -> ConnectionPool:
    """프로세스 전체에서 재사용하는 단일 Connection Pool을 반환한다."""
    global _pool
    if _pool is None:
        _pool = ConnectionPool(_resolve_dsn(dsn), min_size=1, max_size=5, open=True)
    return _pool


def ensure_schema(pool: ConnectionPool | None = None) -> None:
    """pgvector 확장과 document_chunks 테이블이 없으면 만든다."""
    pool = pool or get_connection_pool()
    with pool.connection() as conn:
        conn.execute(_SCHEMA_SQL)
        conn.commit()


_RESERVATION_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS reservations (
    action_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    program TEXT NOT NULL,
    visit_time TEXT NOT NULL,
    headcount INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL,
    decided_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS reservations_user_id_idx ON reservations (user_id);
CREATE INDEX IF NOT EXISTS reservations_status_idx ON reservations (status);

CREATE TABLE IF NOT EXISTS pending_reservation_actions (
    action_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    arguments JSONB NOT NULL,
    summary TEXT NOT NULL,
    approval_status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    decided_at TIMESTAMPTZ
);
"""


def ensure_reservation_schema(pool: ConnectionPool | None = None) -> None:
    """예약/확인대기 테이블(reservations, pending_reservation_actions)이 없으면 만든다."""
    pool = pool or get_connection_pool()
    with pool.connection() as conn:
        conn.execute(_RESERVATION_SCHEMA_SQL)
        conn.commit()


def check_postgres() -> bool:
    """Postgres 연결이 살아있는지 가볍게 확인한다."""
    try:
        pool = get_connection_pool()
        with pool.connection() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False


def _reset_pool_for_tests() -> None:
    """테스트 전용: 캐시된 Pool을 닫고 초기화한다."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
