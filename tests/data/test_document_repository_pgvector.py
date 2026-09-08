"""STORAGE_MODE=persistent 경로의 document_repository를 실제 Postgres로 검증한다."""

from __future__ import annotations

import pytest

from backend.app.core.config import Settings

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _persistent_settings(monkeypatch: pytest.MonkeyPatch):
    from backend.app.core import config as config_module
    from backend.app.core import db as db_module

    db_module._reset_pool_for_tests()
    test_settings = Settings(
        _env_file=None,
        STORAGE_MODE="persistent",
        DATABASE_URL="postgresql://zoo:zoo@127.0.0.1:5432/zoo",
        OPENAI_API_KEY=config_module.get_settings().OPENAI_API_KEY,
    )
    monkeypatch.setattr(config_module, "get_settings", lambda: test_settings)
    monkeypatch.setattr(config_module, "try_get_settings", lambda: test_settings)

    from backend.app.core.db import ensure_schema, get_connection_pool

    pool = get_connection_pool(dsn=test_settings.DATABASE_URL)
    ensure_schema(pool)
    with pool.connection() as conn:
        conn.execute("DELETE FROM document_chunks WHERE collection = 'test_pgvector'")
        conn.commit()
    yield
    with pool.connection() as conn:
        conn.execute("DELETE FROM document_chunks WHERE collection = 'test_pgvector'")
        conn.commit()


def test_insert_then_search_returns_closest_chunk_first() -> None:
    from backend.app.repositories.document_repository import insert_chunks, search
    from backend.app.schemas.tools import ChunkInput

    insert_chunks([
        ChunkInput(
            doc_id="doc-tiger",
            collection="test_pgvector",
            title="호랑이 정보",
            page=None,
            text="호랑이는 맹수관에서 서식하며 육식을 한다.",
            keywords=["호랑이", "맹수관"],
        ),
        ChunkInput(
            doc_id="doc-penguin",
            collection="test_pgvector",
            title="펭귄 정보",
            page=None,
            text="펭귄은 해양관에서 서식하며 물고기를 먹는다.",
            keywords=["펭귄", "해양관"],
        ),
    ])

    results = search("호랑이는 무엇을 먹나요?", "test_pgvector", top_k=2)

    assert len(results) == 2
    assert results[0].doc_id == "doc-tiger"
    assert 0.0 <= results[0].score <= 1.0
    assert results[0].score >= results[1].score
