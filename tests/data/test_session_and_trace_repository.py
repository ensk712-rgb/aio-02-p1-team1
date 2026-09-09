"""C3 확인 테스트: 세션 발급 + Trace 저장 (최두나 소유).

확인 대상: 임의(위조) 세션 거절, TTL, 서로 다른 세션 간 Trace 분리.
"""

from datetime import datetime, timedelta, timezone

import pytest

from backend.app.core.config import Settings
from backend.app.repositories import session_repository, trace_repository

UTC = timezone.utc
T0 = datetime(2026, 9, 5, 4, 0, tzinfo=UTC)  # Asia/Seoul 13:00


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch: pytest.MonkeyPatch):
    """로컬 .env의 persistent 설정과 독립적으로 메모리 저장소를 검증한다."""
    memory_settings = Settings(_env_file=None, STORAGE_MODE="memory")
    monkeypatch.setattr(session_repository, "try_get_settings", lambda: memory_settings)
    monkeypatch.setattr(trace_repository, "try_get_settings", lambda: memory_settings)
    session_repository._reset_for_tests()
    trace_repository._reset_for_tests()
    yield
    session_repository._reset_for_tests()
    trace_repository._reset_for_tests()


# ---- session_repository ----

def test_create_session_returns_unique_unguessable_tokens():
    ids = {session_repository.create_session(now=T0) for _ in range(50)}
    assert len(ids) == 50
    for session_id in ids:
        assert session_id.startswith("guest-")
        assert len(session_id) > len("guest-") + 15  # 최소한의 엔트로피 확인


def test_validate_session_true_for_freshly_created_session():
    session_id = session_repository.create_session(now=T0)
    assert session_repository.validate_session(session_id, now=T0) is True


def test_validate_session_false_for_forged_or_unknown_id():
    assert session_repository.validate_session("guest-forged-token", now=T0) is False
    assert session_repository.validate_session("", now=T0) is False


def test_validate_session_false_after_ttl_expires():
    session_id = session_repository.create_session(now=T0)
    almost_expired = T0 + timedelta(seconds=7199)
    expired = T0 + timedelta(seconds=7201)

    assert session_repository.validate_session(session_id, now=almost_expired) is True
    assert session_repository.validate_session(session_id, now=expired) is False
    # 만료 후 재조회해도 계속 False (등록에서 제거됨)
    assert session_repository.validate_session(session_id, now=expired) is False


def test_session_expiry_clears_associated_trace():
    session_id = session_repository.create_session(now=T0)
    trace_repository.save_run(session_id, "run_1", "completed", [])

    expired = T0 + timedelta(seconds=7201)
    assert session_repository.validate_session(session_id, now=expired) is False
    assert trace_repository.list_runs(session_id) == []


# ---- trace_repository ----

def test_save_and_list_runs_preserve_order():
    trace_repository.save_run("s1", "run_1", "completed", [{"owner": "runtime"}])
    trace_repository.save_run("s1", "run_2", "needs_clarification", [])

    runs = trace_repository.list_runs("s1")
    assert [r["run_id"] for r in runs] == ["run_1", "run_2"]
    assert runs[0]["status"] == "completed"


def test_runs_are_isolated_between_sessions():
    trace_repository.save_run("s1", "run_1", "completed", [])
    trace_repository.save_run("s2", "run_a", "rejected", [])

    assert [r["run_id"] for r in trace_repository.list_runs("s1")] == ["run_1"]
    assert [r["run_id"] for r in trace_repository.list_runs("s2")] == ["run_a"]


def test_unknown_session_returns_empty_list():
    assert trace_repository.list_runs("no-such-session") == []


def test_only_most_recent_20_runs_are_kept_per_session():
    for i in range(25):
        trace_repository.save_run("s1", f"run_{i}", "completed", [])

    runs = trace_repository.list_runs("s1")
    assert len(runs) == 20
    # 가장 오래된 5개(run_0~run_4)는 밀려나고 run_5~run_24만 남아야 한다
    assert [r["run_id"] for r in runs] == [f"run_{i}" for i in range(5, 25)]


def test_recent_summaries_are_masked_ordered_and_outlive_detail_trace():
    trace_repository.save_run(
        "s1",
        "run_1",
        "completed",
        [{"owner": "mcp", "stage": "tool_executed", "data": {"tool": "get_feeding_schedule"}}],
        question="펭귄 먹이시간을 확인하고 싶습니다. 연락처는 010-1234-5678입니다.",
        now=T0,
    )
    trace_repository.save_run("s2", "run_2", "rejected", [], question="삭제해 줘", now=T0 + timedelta(minutes=1))

    summaries = trace_repository.list_recent_summaries(now=T0 + timedelta(minutes=2))

    assert [item["session_id"] for item in summaries] == ["s2", "s1"]
    assert summaries[1]["question_preview"].endswith("…")
    assert "010" not in summaries[1]["question_preview"]
    assert summaries[1]["tools"] == ["get_feeding_schedule"]
    assert trace_repository.get_summary("s1", now=T0 + timedelta(hours=2, minutes=1))
    assert trace_repository.list_recent_summaries(now=T0 + timedelta(hours=24, minutes=2)) == []
