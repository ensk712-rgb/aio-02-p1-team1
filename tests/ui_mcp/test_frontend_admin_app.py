"""별도 관리자 Streamlit 화면 시험."""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[2] / "frontend_admin" / "app.py"


def test_admin_login_and_password_cleanup(monkeypatch) -> None:
    st.cache_resource.clear()
    monkeypatch.setenv("ZOO_UI_FAKE_MODE", "1")
    at = AppTest.from_file(str(APP_PATH), default_timeout=10).run()
    at.text_input(key="admin_login_user_id").set_value("admin")
    at.text_input(key="admin_login_password").set_value("1234")
    at.button[0].click().run()
    assert not at.exception
    assert at.session_state["admin_login_success"] is True
    assert "admin_login_password" not in at.session_state
    assert any("사육사 체험" in item.value for item in at.subheader)


def test_regular_user_cannot_enter_admin_screen(monkeypatch) -> None:
    st.cache_resource.clear()
    monkeypatch.setenv("ZOO_UI_FAKE_MODE", "1")
    at = AppTest.from_file(str(APP_PATH), default_timeout=10).run()
    at.text_input(key="admin_login_user_id").set_value("TEST")
    at.text_input(key="admin_login_password").set_value("1234")
    at.button[0].click().run()
    assert at.session_state["admin_login_success"] is False
    assert any("관리자 권한" in item.value for item in at.error)


def test_admin_can_approve_once(monkeypatch) -> None:
    st.cache_resource.clear()
    monkeypatch.setenv("ZOO_UI_FAKE_MODE", "1")
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["admin_login_success"] = True
    at.session_state["admin_user_id"] = "admin"
    at.session_state["admin_auth_session_id"] = "auth_fake_admin"
    at.run()
    at.button(key="approve_action_fake_001").click().run()
    assert not at.exception
    assert at.session_state["admin_processing_action"] is None
    assert any("예약을 승인했습니다" in success.value for success in at.success)
    assert any("승인 대기 중인 예약이 없습니다" in info.value for info in at.info)


def test_admin_can_reject_once(monkeypatch) -> None:
    st.cache_resource.clear()
    monkeypatch.setenv("ZOO_UI_FAKE_MODE", "1")
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["admin_login_success"] = True
    at.session_state["admin_user_id"] = "admin"
    at.session_state["admin_auth_session_id"] = "auth_fake_admin"
    at.run()
    at.button(key="reject_action_fake_001").click().run()
    assert not at.exception
    assert at.session_state["admin_processing_action"] is None
    assert any("예약을 거절했습니다" in success.value for success in at.success)
    assert any("승인 대기 중인 예약이 없습니다" in info.value for info in at.info)


def test_admin_trace_screen_renders_result(monkeypatch) -> None:
    st.cache_resource.clear()
    monkeypatch.setenv("ZOO_UI_FAKE_MODE", "1")
    at = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at.session_state["admin_login_success"] = True
    at.session_state["admin_user_id"] = "admin"
    at.session_state["admin_auth_session_id"] = "auth_fake_admin"
    at.run()
    assert not at.exception
    assert at.selectbox(key="admin_trace_session_id")
    assert any("run_fake_001" in item.label for item in at.expander)
