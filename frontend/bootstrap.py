"""사용자 앱 전역 Client와 세션 상태 경계."""

from __future__ import annotations

import os
from typing import Any, Protocol

import streamlit as st
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

    def login(self, user_id: str, password: str) -> dict[str, Any]: ...
    def logout(self, auth_session_id: str) -> None: ...
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


load_dotenv(PROJECT_ROOT / ".env")


@st.cache_resource
def get_client() -> AgentClientProtocol:
    if os.getenv("ZOO_UI_FAKE_MODE") == "1":
        return FakeAgentClient()
    return AgentClient(os.getenv("BACKEND_URL", "http://127.0.0.1:8000"))


def initialize_state() -> None:
    defaults = {
        "session_id": None, "messages": [], "login_success": False,
        "user_id": None, "auth_session_id": None, "pending_reservation_action": None,
        "approval_processing": False, "approval_notice": None, "pending_question": None,
        "chat_status": "ready", "route_recommendation_result": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


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
