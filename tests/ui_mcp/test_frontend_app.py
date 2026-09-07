"""Fake Client를 사용하는 Streamlit 화면 단위 시험."""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[2] / "frontend" / "app.py"


def _run_with_question(monkeypatch, question: str) -> AppTest:
    monkeypatch.setenv("ZOO_UI_FAKE_MODE", "1")
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["login_success"] = True
    at.session_state["user_id"] = "TEST"
    at.session_state["auth_session_id"] = "auth_fake"
    at.run()
    at.text_input(key="chat_message_input").set_value(question)
    at.button(key="FormSubmitter:chat_panel_form-보내기").click().run()
    return at


def test_chat_forwards_logged_in_auth_session(monkeypatch) -> None:
    from frontend.clients.fake_agent_client import FakeAgentClient

    captured = []
    original_ask = FakeAgentClient.ask

    def capture_ask(self, message, session_id=None, *, auth_session_id=None):
        captured.append(auth_session_id)
        return original_ask(
            self, message, session_id, auth_session_id=auth_session_id
        )

    monkeypatch.setattr(FakeAgentClient, "ask", capture_ask)
    at = _run_with_question(monkeypatch, "펭귄 먹이시간")
    assert not at.exception
    assert captured == ["auth_fake"]


def test_home_dashboard_renders_design_sections(monkeypatch) -> None:
    monkeypatch.setenv("ZOO_UI_FAKE_MODE", "1")
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["login_success"] = True
    at.session_state["user_id"] = "TEST"
    at.session_state["auth_session_id"] = "auth_fake"
    at.run()
    assert not at.exception
    headings = [item.value for item in at.subheader]
    assert any("먹이주기 일정" in value for value in headings)
    assert any("추천 관람 동선" in value for value in headings)
    assert any("동물 백과" in value for value in headings)
    assert any("AI 가이드 챗봇" in value for value in headings)
    assert any("시연용 Mock" in item.value for item in at.caption)


@pytest.mark.parametrize(
    ("page_path", "expected_text"),
    [
        ("app_pages/animal_info.py", "자이언트 판다"),
        ("app_pages/zoo_map.py", "빠른 위치 찾기"),
        ("app_pages/feeding_schedule.py", "현장 운영"),
        ("app_pages/reservation.py", "예약은 이렇게 진행돼요"),
        ("app_pages/route_recommendation.py", "선택:"),
        ("app_pages/environment.py", "구역별 혼잡도"),
    ],
)
def test_feature_pages_render_from_navigation(monkeypatch, page_path: str, expected_text: str) -> None:
    monkeypatch.setenv("ZOO_UI_FAKE_MODE", "1")
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["login_success"] = True
    at.session_state["user_id"] = "TEST"
    at.session_state["auth_session_id"] = "auth_fake"
    at.run().switch_page(page_path).run()
    assert not at.exception
    visible_text = [item.value for collection in (at.markdown, at.subheader, at.caption, at.warning) for item in collection]
    assert any(expected_text in value for value in visible_text)
    assert any("시연용 Mock" in item.value for item in at.caption)


def test_reservation_page_labels_live_backend_mode(monkeypatch) -> None:
    monkeypatch.setenv("ZOO_UI_FAKE_MODE", "0")
    monkeypatch.setenv("BACKEND_URL", "http://127.0.0.1:9")
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["login_success"] = True
    at.session_state["user_id"] = "TEST"
    at.session_state["auth_session_id"] = "auth_test"
    at.run().switch_page("app_pages/reservation.py").run()
    assert not at.exception
    assert any("실제 Backend API" in item.value for item in at.caption)
    assert not any("시연용 Mock 모드" in item.value for item in at.caption)


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


@pytest.mark.parametrize(
    ("question", "expected_label"),
    [
        ("client_connection", "서버 연결 실패"),
        ("client_timeout", "응답 지연"),
        ("client_http", "API 요청 실패"),
        ("client_invalid_response", "응답 형식 오류"),
    ],
)
def test_client_failures_have_distinct_error_labels(monkeypatch, question: str, expected_label: str) -> None:
    at = _run_with_question(monkeypatch, question)
    assert not at.exception
    assert any(expected_label in item.value for item in at.markdown)
    assert any(message.get("response", {}).get("error_kind") for message in at.session_state["messages"] if message["role"] == "assistant")
    assert not any("확인 완료" in item.value for item in at.markdown)


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
    assert at.session_state["chat_status"] == "ready"


def test_chat_history_supports_multiple_tool_responses(monkeypatch) -> None:
    at = _run_with_question(monkeypatch, "펭귄 먹이시간")
    at.text_input(key="chat_message_input").set_value("해양관 펭귄 먹이시간")
    at.button(key="FormSubmitter:chat_panel_form-보내기").click().run()
    assert not at.exception
    assert len(at.session_state["messages"]) == 4
    assert at.session_state["chat_status"] == "ready"


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
    at.button(key="FormSubmitter:reservation_request-예약 내용 확인").click().run()
    action = at.session_state["pending_reservation_action"]
    assert action["approval_status"] == "pending"
    assert at.get("progress") and at.get("progress")[-1].value > 0
    assert any("서버 만료 시각" in caption.value for caption in at.caption)
    assert any("확인 전에는 예약이 생성" in caption.value for caption in at.caption)
    at.button(key=f"confirm_{action['action_id']}").click().run()
    assert not at.exception
    assert at.session_state["pending_reservation_action"] is None
    assert any("관리자에게 전달" in success.value for success in at.success)


def test_reservation_confirmation_can_be_cancelled(monkeypatch) -> None:
    monkeypatch.setenv("ZOO_UI_FAKE_MODE", "1")
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["login_success"] = True
    at.session_state["user_id"] = "TEST"
    at.session_state["auth_session_id"] = "auth_fake"
    at.run()
    at.button(key="FormSubmitter:reservation_request-예약 내용 확인").click().run()
    action_id = at.session_state["pending_reservation_action"]["action_id"]
    at.button(key=f"cancel_{action_id}").click().run()
    assert not at.exception
    assert at.session_state["pending_reservation_action"] is None
    assert any("취소했습니다" in info.value for info in at.info)
