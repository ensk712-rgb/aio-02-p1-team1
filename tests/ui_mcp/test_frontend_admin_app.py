"""별도 관리자 Streamlit 화면 시험."""

from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[2] / "frontend_admin" / "app.py"


def test_admin_login_and_password_cleanup(monkeypatch) -> None:
    monkeypatch.setenv("ZOO_UI_FAKE_MODE", "1")
    at = AppTest.from_file(str(APP_PATH), default_timeout=10).run()
    at.text_input(key="admin_login_user_id").set_value("TEST")
    at.text_input(key="admin_login_password").set_value("1234")
    at.button[0].click().run()
    assert not at.exception
    assert at.session_state["admin_login_success"] is True
    assert "admin_login_password" not in at.session_state
    assert any("사육사 체험" in item.value for item in at.subheader)


def test_admin_can_approve_once(monkeypatch) -> None:
    monkeypatch.setenv("ZOO_UI_FAKE_MODE", "1")
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["admin_login_success"] = True
    at.session_state["admin_user_id"] = "TEST"
    at.session_state["admin_auth_session_id"] = "auth_fake"
    at.run()
    at.button(key="approve_action_fake_001").click().run()
    assert not at.exception
    assert any("승인 대기 중인 예약이 없습니다" in info.value for info in at.info)
