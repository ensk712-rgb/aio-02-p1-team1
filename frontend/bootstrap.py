"""사용자 앱 전역 Client와 세션 상태 경계."""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any, Protocol

import streamlit as st
import extra_streamlit_components as stx
from dotenv import load_dotenv

from backend.app.core.config import PROJECT_ROOT
from frontend.clients.agent_client import AgentClient, AgentClientError
from frontend.clients.fake_agent_client import FakeAgentClient


class AgentClientProtocol(Protocol):
    def get_health(self) -> dict[str, Any]: ...

    def ask(
        self,
        message: str,
        session_id: str | None = None,
        *,
        auth_session_id: str | None = None,
    ) -> dict[str, Any]: ...

    def ask_stream(
        self,
        message: str,
        session_id: str | None = None,
        *,
        auth_session_id: str | None = None,
    ) -> Iterator[dict[str, Any]]: ...

    def login(self, user_id: str, password: str) -> dict[str, Any]: ...
    def logout(self, auth_session_id: str) -> None: ...
    def get_auth_session(self, auth_session_id: str) -> dict[str, Any]: ...
    def create_reservation(self, auth_session_id: str, **payload: Any) -> dict[str, Any]: ...
    def confirm_reservation(self, auth_session_id: str, action_id: str, decision: str) -> dict[str, Any]: ...
    def get_my_reservations(self, auth_session_id: str) -> dict[str, Any]: ...

    def get_course_info(
        self,
        *,
        available_minutes: int,
        child_accompanying: bool = False,
        current: str = "정문",
    ) -> dict[str, Any]: ...

    def get_habitat_route(self, current: str, destination: str) -> dict[str, Any]: ...
    def get_closure_status(self, habitat: str | None = None) -> dict[str, Any]: ...

    def analyze_animal_image(
        self, image_bytes: bytes, *, filename: str, content_type: str
    ) -> dict[str, Any]: ...


load_dotenv(PROJECT_ROOT / ".env")
AUTH_COOKIE = "zoo_auth_session"
_cookie_manager: stx.CookieManager | None = None


def initialize_cookie_manager() -> stx.CookieManager:
    """매 실행마다 쿠키 값을 다시 읽고 같은 실행 안에서는 객체를 재사용한다."""
    global _cookie_manager
    _cookie_manager = stx.CookieManager(key="zoo_auth_cookie_manager")
    return _cookie_manager


def get_cookie_manager() -> stx.CookieManager:
    global _cookie_manager
    if _cookie_manager is None:
        _cookie_manager = stx.CookieManager(key="zoo_auth_cookie_manager")
    return _cookie_manager


@st.cache_resource
def get_client() -> AgentClientProtocol:
    if os.getenv("ZOO_UI_FAKE_MODE") == "1":
        return FakeAgentClient()
    return AgentClient(os.getenv("BACKEND_URL", "http://192.100.200.198:8000/"))


def initialize_state() -> None:
    defaults = {
        "session_id": None, "messages": [], "login_success": False,
        "user_id": None, "auth_session_id": None, "pending_reservation_action": None,
        "approval_processing": False, "approval_notice": None, "pending_question": None,
        "chat_status": "ready", "route_recommendation_result": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def restore_login() -> None:
    """F5로 새 Streamlit 세션이 생성되면 쿠키를 서버에서 검증해 로그인만 복원한다."""
    if st.session_state.login_success:
        return
    token = get_cookie_manager().get(AUTH_COOKIE)
    if not isinstance(token, str) or not token:
        return
    try:
        result = get_client().get_auth_session(token)
    except AgentClientError:
        forget_login()
        return
    if result.get("success") is True and isinstance(result.get("user_id"), str):
        st.session_state.login_success = True
        st.session_state.user_id = result["user_id"]
        st.session_state.auth_session_id = token


def remember_login(auth_session_id: str) -> None:
    """비밀번호가 아닌 불투명 세션 ID만 브라우저에 저장한다."""
    get_cookie_manager().set(
        AUTH_COOKIE,
        auth_session_id,
        key="remember_zoo_login",
        max_age=7200,
        same_site="strict",
    )


def forget_login() -> None:
    manager = get_cookie_manager()
    if manager.get(AUTH_COOKIE) is not None:
        manager.delete(AUTH_COOKIE, key="forget_zoo_login")


def reset_conversation() -> None:
    st.session_state.session_id = None
    st.session_state.messages = []
    st.session_state.chat_status = "ready"


def logout() -> None:
    token = st.session_state.get("auth_session_id")
    if token:
        try:
            get_client().logout(token)
        except AgentClientError:
            pass
    forget_login()
    st.session_state.login_success = False
    st.session_state.user_id = None
    st.session_state.auth_session_id = None
    st.session_state.pending_reservation_action = None
    st.session_state.approval_processing = False
    st.session_state.approval_notice = None
    st.session_state.pending_question = None
    st.session_state.chat_status = "ready"
    st.session_state.route_recommendation_result = None
    reset_conversation()
