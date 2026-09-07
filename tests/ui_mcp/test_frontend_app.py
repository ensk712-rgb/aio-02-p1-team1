"""Fake Client를 사용하는 Streamlit 화면 단위 시험."""

from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[2] / "frontend" / "app.py"


def _run_with_question(monkeypatch, question: str) -> AppTest:
    monkeypatch.setenv("ZOO_UI_FAKE_MODE", "1")
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["login_success"] = True
    at.session_state["user_id"] = "TEST"
    at.session_state["auth_session_id"] = "auth_fake"
    at.run()
    at.chat_input(key="question").set_value(question).run()
    return at


def test_completed_renders_sources_and_tool_card(monkeypatch) -> None:
    at = _run_with_question(monkeypatch, "펭귄 먹이시간")
    assert not at.exception
    assert any("확인 완료" in item.value for item in at.markdown)
    assert any("운영 정보 확인" in subheader.value for subheader in at.subheader)
    assert any("자료" in frame.value.columns for frame in at.dataframe)


def test_error_is_not_rendered_as_success(monkeypatch) -> None:
    at = _run_with_question(monkeypatch, "error")
    assert not at.exception
    assert any("조회 실패" in item.value for item in at.markdown)
    assert any("운영 정보를 확인하지 못했습니다" in error.value for error in at.error)
    assert not any("운영 정보 확인" in subheader.value for subheader in at.subheader)


def test_needs_clarification_renders_actionable_warning(monkeypatch) -> None:
    at = _run_with_question(monkeypatch, "needs_clarification")
    assert not at.exception
    assert any("정보 필요" in item.value for item in at.markdown)
    assert any("출발 위치와 목적지" in warning.value for warning in at.warning)


def test_new_conversation_clears_messages_and_session(monkeypatch) -> None:
    at = _run_with_question(monkeypatch, "펭귄 먹이시간")
    assert at.session_state["session_id"] == "session_fake_001"
    at.button(key="new_conversation").click().run()
    assert at.session_state["session_id"] is None
    assert at.session_state["messages"] == []


def test_login_success_is_saved_without_password(monkeypatch) -> None:
    monkeypatch.setenv("ZOO_UI_FAKE_MODE", "1")
    at = AppTest.from_file(str(APP_PATH), default_timeout=10).run()
    at.text_input(key="login_user_id").set_value("TEST")
    at.text_input(key="login_password").set_value("1234")
    at.button[0].click().run()
    assert not at.exception
    assert at.session_state["login_success"] is True
    assert at.session_state["user_id"] == "TEST"
    assert "login_password" not in at.session_state


def test_reservation_confirmation_card_and_confirm(monkeypatch) -> None:
    monkeypatch.setenv("ZOO_UI_FAKE_MODE", "1")
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["login_success"] = True
    at.session_state["user_id"] = "TEST"
    at.session_state["auth_session_id"] = "auth_fake"
    at.run()
    at.button(key="FormSubmitter:reservation_request-승인 요청").click().run()
    action = at.session_state["pending_reservation_action"]
    assert action["approval_status"] == "pending"
    at.button(key=f"confirm_{action['action_id']}").click().run()
    assert not at.exception
    assert at.session_state["pending_reservation_action"] is None
    assert any("관리자에게 전달" in info.value for info in at.info)


def test_reservation_confirmation_can_be_cancelled(monkeypatch) -> None:
    monkeypatch.setenv("ZOO_UI_FAKE_MODE", "1")
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["login_success"] = True
    at.session_state["user_id"] = "TEST"
    at.session_state["auth_session_id"] = "auth_fake"
    at.run()
    at.button(key="FormSubmitter:reservation_request-승인 요청").click().run()
    action_id = at.session_state["pending_reservation_action"]["action_id"]
    at.button(key=f"cancel_{action_id}").click().run()
    assert not at.exception
    assert at.session_state["pending_reservation_action"] is None
    assert any("취소했습니다" in info.value for info in at.info)
