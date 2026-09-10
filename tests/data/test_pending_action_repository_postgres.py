"""PostgresPendingActionRepository를 실제 Postgres로 검증한다."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.app.core.config import Settings

pytestmark = pytest.mark.integration

T0 = datetime(2026, 9, 5, 4, 0, tzinfo=timezone.utc)


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
        conn.execute("DELETE FROM pending_reservation_actions")
        conn.commit()
    yield
    with pool.connection() as conn:
        conn.execute("DELETE FROM pending_reservation_actions")
        conn.commit()


def _repo(now_value: list[datetime]):
    from backend.app.repositories.pending_action_repository import PostgresPendingActionRepository

    return PostgresPendingActionRepository(ttl_seconds=120, now=lambda: now_value[0])


def test_create_returns_public_item_without_session_id() -> None:
    now = [T0]
    repo = _repo(now)
    item = repo.create(
        session_id="guest-1", tool_name="reserve_experience_program",
        arguments={"program": "사육사 체험", "headcount": 2}, summary="15:00 사육사 체험 · 2명",
    )
    assert "session_id" not in item
    assert item["approval_status"] == "pending"
    assert item["arguments"] == {"program": "사육사 체험", "headcount": 2}
    assert item["expires_at"] == (T0 + timedelta(seconds=120)).isoformat()


def test_decide_confirm_transitions_to_processing_and_complete_finishes() -> None:
    now = [T0]
    repo = _repo(now)
    item = repo.create(
        session_id="guest-1", tool_name="reserve_experience_program",
        arguments={"program": "사육사 체험"}, summary="요약",
    )
    outcome, result = repo.decide(item["action_id"], session_id="guest-1", decision="confirm")
    assert outcome == "ready"
    assert result["approval_status"] == "processing"

    completed = repo.complete(item["action_id"])
    assert completed["approval_status"] == "completed"


def test_decide_rejects_session_mismatch_without_changing_status() -> None:
    now = [T0]
    repo = _repo(now)
    item = repo.create(
        session_id="guest-1", tool_name="reserve_experience_program",
        arguments={}, summary="요약",
    )
    outcome, result = repo.decide(item["action_id"], session_id="guest-FORGED", decision="confirm")
    assert outcome == "session_mismatch"
    assert result is None


def test_decide_expired_marks_expired_once_ttl_passes() -> None:
    now = [T0]
    repo = _repo(now)
    item = repo.create(
        session_id="guest-1", tool_name="reserve_experience_program",
        arguments={}, summary="요약",
    )
    now[0] = T0 + timedelta(seconds=121)
    outcome, result = repo.decide(item["action_id"], session_id="guest-1", decision="confirm")
    assert outcome == "expired"
    assert result["approval_status"] == "expired"


def test_decide_not_found_for_unknown_action_id() -> None:
    now = [T0]
    repo = _repo(now)
    outcome, result = repo.decide("action_unknown", session_id="guest-1", decision="confirm")
    assert outcome == "not_found"
    assert result is None


def test_decide_already_processed_on_second_confirm() -> None:
    now = [T0]
    repo = _repo(now)
    item = repo.create(
        session_id="guest-1", tool_name="reserve_experience_program",
        arguments={}, summary="요약",
    )
    repo.decide(item["action_id"], session_id="guest-1", decision="confirm")
    outcome, result = repo.decide(item["action_id"], session_id="guest-1", decision="confirm")
    assert outcome == "already_processed"
    assert result["approval_status"] == "processing"
