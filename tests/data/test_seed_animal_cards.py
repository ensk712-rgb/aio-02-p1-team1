"""`backend/scripts/seed_animal_cards.py`로 적재한 동물 카드 100건을 실제 Postgres로 검증한다.

`tests/data/test_document_repository_pgvector.py`와 같은 패턴(STORAGE_MODE=persistent,
실제 DB 필요)을 따르되, 임의의 테스트 컬렉션이 아니라 실제 시딩 결과물인
`collection="animal_cards"`가 기대한 개수·형태로 들어가 있는지 확인한다.

실행 전제:
- infra/docker-compose.yml의 postgres가 떠 있어야 한다.
- `python backend/scripts/seed_animal_cards.py`로 시딩이 이미 끝나 있어야 한다.
- OPENAI_API_KEY가 .env에 설정되어 있어야 한다 (search()가 질의를 임베딩해야 함).

실행: pytest -m integration tests/data/test_seed_animal_cards.py
"""

from __future__ import annotations

import pytest

from backend.app.core.config import Settings

pytestmark = pytest.mark.integration

EXPECTED_CARD_COUNT = 100


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
    yield


def test_document_chunks_has_all_seeded_animal_cards() -> None:
    from backend.app.core.db import get_connection_pool

    pool = get_connection_pool()
    with pool.connection() as conn:
        row = conn.execute(
            "SELECT count(*) FROM document_chunks WHERE collection = %s",
            ("animal_cards",),
        ).fetchone()

    assert row is not None
    assert row[0] >= EXPECTED_CARD_COUNT


def test_document_chunks_embedding_has_expected_dimension() -> None:
    from backend.app.core.db import get_connection_pool

    pool = get_connection_pool()
    with pool.connection() as conn:
        row = conn.execute(
            """
            SELECT vector_dims(embedding)
            FROM document_chunks
            WHERE collection = %s
            LIMIT 1
            """,
            ("animal_cards",),
        ).fetchone()

    assert row is not None
    assert row[0] == 1536


def test_search_panda_query_returns_panda_card_first() -> None:
    from backend.app.repositories.document_repository import search

    results = search("판다는 무엇을 먹어?", "animal_cards", top_k=3)

    assert len(results) == 3
    assert results[0].doc_id == "ANIMAL-PANDA"
    assert 0.0 <= results[0].score <= 1.0
    assert results[0].collection == "animal_cards"


def test_search_respects_top_k_and_ordering() -> None:
    from backend.app.repositories.document_repository import search

    results = search("호랑이는 어디서 살아?", "animal_cards", top_k=5)

    assert len(results) == 5
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)
