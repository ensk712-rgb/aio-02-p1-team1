"""Fake Client를 사용하는 Streamlit 화면 단위 시험."""

from __future__ import annotations

from pathlib import Path
from datetime import datetime, timedelta, timezone

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
    at.text_input(key="hero_question").set_value(question)
    at.button(key="FormSubmitter:hero_question_form-AI에게 질문하기").click().run()
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
        ("app_pages/feeding_schedule.py", "현장 운영"),
        ("app_pages/reservation.py", "예약은 이렇게 진행돼요"),
        ("app_pages/environment.py", "일기예보"),
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
    monkeypatch.setenv("BACKEND_URL", "http://192.100.200.198:8000/")
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
    at.text_input(key="hero_question").set_value("해양관 펭귄 먹이시간")
    at.button(key="FormSubmitter:hero_question_form-AI에게 질문하기").click().run()
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
    at.run().switch_page("app_pages/reservation.py").run()
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


def test_chat_reservation_confirmation_is_actionable_and_localized(monkeypatch) -> None:
    from frontend.clients.fake_agent_client import FakeAgentClient

    def reservation_answer(self, message, session_id=None, *, auth_session_id=None):
        result = self.create_reservation(
            auth_session_id,
            program="사육사 체험",
            visit_time="2026-09-11T15:00:00+09:00",
            headcount=2,
        )
        action = result["pending_action"]
        # 서버·브라우저 시각의 미세한 차이로 120초를 잠시 넘는 상황도 재현한다.
        action["expires_at"] = (datetime.now(timezone.utc) + timedelta(seconds=121)).isoformat()
        self._pending_action["expires_at"] = action["expires_at"]
        return {
            "session_id": session_id or "session_fake_reservation",
            "status": "confirmation_required",
            "final_answer": "예약 내용을 확인한 뒤 확인 또는 취소를 선택해 주세요.",
            "sources": [],
            "tool_calls": [{
                "name": "reserve_experience_program",
                "result": {
                    "success": True,
                    "data": {"pending_action": action},
                    "source": "backend_approval",
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                },
            }],
            "pending_action": action,
        }

    monkeypatch.setattr(FakeAgentClient, "ask", reservation_answer)
    at = _run_with_question(monkeypatch, "9월 11일 오후 3시 사육사 체험 2명 예약")

    assert not at.exception
    assert not any("예약 내용을 확인" in error.value for error in at.error)
    assert any("확인 대기" in item.value for item in at.markdown)
    tables = [table.value for table in at.table]
    assert any("항목" in table.columns and "진행 상태" in table["항목"].values for table in tables)
    assert any("KST" in str(table.to_dict()) for table in tables)
    action_id = at.session_state["pending_reservation_action"]["action_id"]
    assert any(progress.value == 100 for progress in at.get("progress"))

    at.button(key=f"chat_1_confirm_{action_id}").click().run()
    assert not at.exception
    assert at.session_state["pending_reservation_action"] is None
    assert any("관리자에게 전달" in success.value for success in at.success)


def test_zoo_map_renders_open_habitat_route_by_default(monkeypatch) -> None:

    """기본 선택(정문 → 해양관)은 휴장이 아니므로 실제 경로가 표시된다."""

    monkeypatch.setenv("ZOO_UI_FAKE_MODE", "1")
    at = AppTest.from_file(str(APP_PATH), default_timeout=20)
    at.session_state["login_success"] = True
    at.session_state["user_id"] = "TEST"
    at.session_state["auth_session_id"] = "auth_fake"
    at.run().switch_page("app_pages/zoo_map.py").run()
    assert not at.exception

    assert at.selectbox(key="map_route_start").value == "정문"
    assert at.selectbox(key="map_route_destination").value == "해양관"
    assert any("정문 → 해양관 · 도보 약 15분" in success.value for success in at.success)


def test_zoo_map_shows_closure_warning_for_closed_habitat(monkeypatch) -> None:
    monkeypatch.setenv("ZOO_UI_FAKE_MODE", "1")
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["login_success"] = True
    at.session_state["user_id"] = "TEST"
    at.session_state["auth_session_id"] = "auth_fake"
    at.run().switch_page("app_pages/zoo_map.py").run()

    at.selectbox(key="map_route_destination").set_value("코끼리관").run()

    
    assert not at.exception
    assert any("휴장 중입니다" in warning.value for warning in at.warning)
    assert any("시설 점검" in warning.value for warning in at.warning)
    assert not at.success


def test_route_recommendation_renders_form_without_calling_backend(monkeypatch) -> None:
    """제출 전에는 Client를 호출하지 않고 입력 폼만 보여준다."""
    monkeypatch.setenv("ZOO_UI_FAKE_MODE", "1")
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["login_success"] = True
    at.session_state["user_id"] = "TEST"
    at.session_state["auth_session_id"] = "auth_fake"
    at.run().switch_page("app_pages/route_recommendation.py").run()
    assert not at.exception
    assert at.number_input(key="route_available_minutes") is not None
    assert at.session_state["route_recommendation_result"] is None


def test_route_recommendation_submit_renders_fake_course_result(monkeypatch) -> None:
    monkeypatch.setenv("ZOO_UI_FAKE_MODE", "1")
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["login_success"] = True
    at.session_state["user_id"] = "TEST"
    at.session_state["auth_session_id"] = "auth_fake"
    at.run().switch_page("app_pages/route_recommendation.py").run()
    at.button(key="FormSubmitter:route_recommendation_form-추천 동선 보기").click().run()
    assert not at.exception
    result = at.session_state["route_recommendation_result"]
    assert result["success"] is True
    assert result["data"]["facility_scope"] == "all"
    assert any("해양관" in item.value for item in at.markdown)
    assert any("총 소요 시간" in item.value for item in at.caption)


def test_route_recommendation_shows_empty_result_notice(monkeypatch) -> None:
    """stops=[]일 때 실패처럼 보이지 않는 안내 문구를 표시한다(§7)."""
    monkeypatch.setenv("ZOO_UI_FAKE_MODE", "1")
    from frontend.clients.fake_agent_client import FakeAgentClient

    def _empty_course_info(self, *, available_minutes, child_accompanying=False, current="정문"):
        return {
            "success": True,
            "data": {
                "current": current,
                "available_minutes": available_minutes,
                "facility_scope": "all",
                "stops": [],
                "total_minutes": 0,
                "remaining_minutes": available_minutes,
                "weather_lookup_succeeded": True,
            },
            "error": None,
            "source": "mock_zoo_operations",
            "retrieved_at": "2026-09-09T00:00:00+00:00",
        }

    monkeypatch.setattr(FakeAgentClient, "get_course_info", _empty_course_info)
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["login_success"] = True
    at.session_state["user_id"] = "TEST"
    at.session_state["auth_session_id"] = "auth_fake"
    at.run().switch_page("app_pages/route_recommendation.py").run()
    at.button(key="FormSubmitter:route_recommendation_form-추천 동선 보기").click().run()
    assert not at.exception
    assert any("가능한 코스를 만들기 어렵습니다" in warning.value for warning in at.warning)


def test_route_recommendation_shows_indoor_only_notice(monkeypatch) -> None:
    monkeypatch.setenv("ZOO_UI_FAKE_MODE", "1")
    from frontend.clients.fake_agent_client import FakeAgentClient

    def _indoor_only_course_info(self, *, available_minutes, child_accompanying=False, current="정문"):
        return {
            "success": True,
            "data": {
                "current": current,
                "available_minutes": available_minutes,
                "facility_scope": "indoor_only",
                "stops": [
                    {
                        "habitat": "해양관",
                        "travel_minutes": 15,
                        "visit_minutes": 25,
                        "cumulative_minutes": 40,
                    }
                ],
                "total_minutes": 40,
                "remaining_minutes": available_minutes - 40,
            },
            "error": None,
            "source": "mock_zoo_operations",
            "retrieved_at": "2026-09-09T00:00:00+00:00",
        }

    monkeypatch.setattr(FakeAgentClient, "get_course_info", _indoor_only_course_info)
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["login_success"] = True
    at.session_state["user_id"] = "TEST"
    at.session_state["auth_session_id"] = "auth_fake"
    at.run().switch_page("app_pages/route_recommendation.py").run()
    at.button(key="FormSubmitter:route_recommendation_form-추천 동선 보기").click().run()
    assert not at.exception
    assert any("실내에서 관람 가능한 코스만" in info.value for info in at.info)


def test_logout_clears_route_recommendation_result(monkeypatch) -> None:
    """로그아웃 후 다른 계정으로 들어와도 이전 사용자의 코스 카드가 남지 않아야 한다."""
    monkeypatch.setenv("ZOO_UI_FAKE_MODE", "1")
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["login_success"] = True
    at.session_state["user_id"] = "TEST"
    at.session_state["auth_session_id"] = "auth_fake"
    at.run().switch_page("app_pages/route_recommendation.py").run()
    at.button(key="FormSubmitter:route_recommendation_form-추천 동선 보기").click().run()
    assert at.session_state["route_recommendation_result"] is not None

    at.button(key="logout_route").click().run()
    assert not at.exception
    assert at.session_state["route_recommendation_result"] is None


def test_additional_feature_pages_render(monkeypatch) -> None:
    monkeypatch.setenv("ZOO_UI_FAKE_MODE", "1")
    for page, expected in (
        ("app_pages/voice_assistant.py", "음성 안내"),
        ("app_pages/image_analysis.py", "이미지 인식 분석"),
        ("app_pages/notice.py", "안내 및 주의사항"),
        ("app_pages/refund.py", "취소 및 환불"),
    ):
        at = AppTest.from_file(str(APP_PATH), default_timeout=10)
        at.session_state["login_success"] = True
        at.session_state["user_id"] = "TEST"
        at.session_state["auth_session_id"] = "auth_fake"
        at.run().switch_page(page).run()
        assert not at.exception
        assert any(expected in title.value for title in at.title)


def test_voice_page_contains_agent_answer_controls() -> None:
    source = (APP_PATH.parent / "app_pages" / "voice_assistant.py").read_text(encoding="utf-8")
    assert "AI에게 질문하기" in source
    assert "AI 안내 답변" in source
    assert "답변 듣기" in source
    assert "/api/agent/ask" in source


def test_reservation_confirmation_can_be_cancelled(monkeypatch) -> None:
    monkeypatch.setenv("ZOO_UI_FAKE_MODE", "1")
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["login_success"] = True
    at.session_state["user_id"] = "TEST"
    at.session_state["auth_session_id"] = "auth_fake"
    at.run().switch_page("app_pages/reservation.py").run()
    at.button(key="FormSubmitter:reservation_request-예약 내용 확인").click().run()
    action_id = at.session_state["pending_reservation_action"]["action_id"]
    at.button(key=f"cancel_{action_id}").click().run()
    assert not at.exception
    assert at.session_state["pending_reservation_action"] is None
    assert any("취소했습니다" in info.value for info in at.info)
