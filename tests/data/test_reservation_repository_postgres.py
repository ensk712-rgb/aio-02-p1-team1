"""PostgresReservationRepository를 실제 Postgres로 검증한다."""

from __future__ import annotations

import pytest

from backend.app.core.config import Settings

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _persistent_db(monkeypatch: pytest.MonkeyPatch):
    from backend.app.core import config as config_module
    from backend.app.core import db as db_module

    db_module._reset_pool_for_tests()
    test_settings = Settings(
        _env_file=None,
        RESERVATION_STORAGE_MODE="persistent",
        DATABASE_URL="postgresql://zoo:zoo@127.0.0.1:5432/zoo",
    )
    monkeypatch.setattr(config_module, "get_settings", lambda: test_settings)

    from backend.app.core.db import ensure_reservation_schema, get_connection_pool

    pool = get_connection_pool(dsn=test_settings.DATABASE_URL)
    ensure_reservation_schema(pool)
    with pool.connection() as conn:
        conn.execute("DELETE FROM reservations")
        conn.commit()
    yield
    with pool.connection() as conn:
        conn.execute("DELETE FROM reservations")
        conn.commit()


def test_create_then_list_for_user_returns_created_reservation() -> None:
    from backend.app.repositories.reservation_repository import PostgresReservationRepository

    repo = PostgresReservationRepository()
    created = repo.create(user_id="TEST", program="사육사 체험", visit_time="15:00", headcount=2)

    assert created["status"] == "pending"
    assert created["decided_at"] is None
    assert created["action_id"].startswith("action_")

    mine = repo.list_for_user("TEST")
    assert len(mine) == 1
    assert mine[0]["action_id"] == created["action_id"]
    assert mine[0]["program"] == "사육사 체험"

    others = repo.list_for_user("OTHER")
    assert others == []


def test_list_pending_only_returns_pending_status() -> None:
    from backend.app.repositories.reservation_repository import PostgresReservationRepository

    repo = PostgresReservationRepository()
    pending = repo.create(user_id="TEST", program="사육사 체험", visit_time="15:00", headcount=1)
    to_decide = repo.create(user_id="TEST", program="먹이 주기", visit_time="11:00", headcount=1)
    repo.decide(to_decide["action_id"], "approve")

    action_ids = {item["action_id"] for item in repo.list_pending()}
    assert pending["action_id"] in action_ids
    assert to_decide["action_id"] not in action_ids


def test_decide_is_atomic_under_concurrent_double_decision() -> None:
    """같은 action_id에 동시에 결정이 들어와도 정확히 한 번만 반영돼야 한다."""
    from concurrent.futures import ThreadPoolExecutor

    from backend.app.repositories.reservation_repository import PostgresReservationRepository

    repo = PostgresReservationRepository()
    created = repo.create(user_id="TEST", program="사육사 체험", visit_time="15:00", headcount=1)

    with ThreadPoolExecutor(max_workers=2) as pool_exec:
        futures = [
            pool_exec.submit(repo.decide, created["action_id"], "approve"),
            pool_exec.submit(repo.decide, created["action_id"], "reject"),
        ]
        results = [future.result() for future in futures]

    succeeded = [result for result in results if result is not None]
    assert len(succeeded) == 1  # 둘 중 하나만 반영되고 나머지는 None(이미 처리됨)
    assert succeeded[0]["status"] in {"approved", "rejected"}

    stored = repo.list_for_user("TEST")[0]
    assert stored["status"] == succeeded[0]["status"]
