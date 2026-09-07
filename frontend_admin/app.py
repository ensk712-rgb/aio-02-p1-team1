"""예약 승인 전용 Streamlit 관리자 화면."""

from __future__ import annotations

import os

import streamlit as st
from dotenv import load_dotenv

from backend.app.core.config import PROJECT_ROOT
from frontend.clients.agent_client import AgentClient, AgentClientError
from frontend.clients.fake_agent_client import FakeAgentClient


load_dotenv(PROJECT_ROOT / ".env")

st.set_page_config(
    page_title="Zoo Visit Guide 관리자",
    page_icon=":material/admin_panel_settings:",
    layout="wide",
)


@st.cache_resource
def get_client():
    if os.getenv("ZOO_UI_FAKE_MODE") == "1":
        return FakeAgentClient()
    return AgentClient(os.getenv("BACKEND_URL", "http://127.0.0.1:8000"))


def initialize_state() -> None:
    st.session_state.setdefault("admin_login_success", False)
    st.session_state.setdefault("admin_user_id", None)
    st.session_state.setdefault("admin_auth_session_id", None)


def logout() -> None:
    token = st.session_state.get("admin_auth_session_id")
    if token:
        try:
            get_client().logout(token)
        except AgentClientError:
            pass
    st.session_state.admin_login_success = False
    st.session_state.admin_user_id = None
    st.session_state.admin_auth_session_id = None


initialize_state()
client = get_client()

if not st.session_state.admin_login_success:
    st.title("관리자 로그인", icon=":material/admin_panel_settings:")
    st.caption("예약 승인 업무를 시작하려면 로그인하세요.")
    with st.form("admin_login"):
        user_id = st.text_input("아이디", key="admin_login_user_id")
        password = st.text_input("비밀번호", type="password", key="admin_login_password")
        submitted = st.form_submit_button("관리자 로그인", icon=":material/login:")
    if submitted:
        try:
            result = client.login(user_id, password)
            st.session_state.admin_login_success = result.get("success") is True
            st.session_state.admin_user_id = result.get("user_id")
            st.session_state.admin_auth_session_id = result.get("auth_session_id")
            st.rerun()
        except AgentClientError as error:
            st.error(str(error), icon=":material/error:")
    st.stop()

st.session_state.pop("admin_login_password", None)
st.session_state.pop("admin_login_user_id", None)

with st.container(horizontal=True, vertical_alignment="center"):
    st.title("예약 승인 안내소", icon=":material/approval:")
    st.button("로그아웃", icon=":material/logout:", on_click=logout, key="admin_logout")

st.caption(f"담당 계정 · {st.session_state.admin_user_id}")

try:
    items = client.get_pending_reservations(st.session_state.admin_auth_session_id).get("items", [])
except AgentClientError as error:
    st.error(str(error), icon=":material/error:")
    st.stop()

if not items:
    st.info("현재 승인 대기 중인 예약이 없습니다.", icon=":material/inbox:")

for item in items:
    action_id = str(item.get("action_id", ""))
    with st.container(border=True, key=f"reservation_{action_id}"):
        st.subheader(str(item.get("program", "예약 프로그램")), icon=":material/event:")
        st.table(
            {
                "신청 계정": str(item.get("user_id", "-")),
                "예약 시간": str(item.get("visit_time", "-")),
                "인원": str(item.get("headcount", "-")),
                "상태": "승인 대기",
            },
            border="horizontal",
            width="content",
        )
        with st.container(horizontal=True):
            if st.button("승인", type="primary", icon=":material/check:", key=f"approve_{action_id}"):
                try:
                    client.decide_reservation(
                        st.session_state.admin_auth_session_id, action_id, "approve"
                    )
                    st.toast("예약을 승인했습니다.", icon=":material/check_circle:")
                    st.rerun()
                except AgentClientError as error:
                    st.error(str(error), icon=":material/error:")
            if st.button("거절", icon=":material/close:", key=f"reject_{action_id}"):
                try:
                    client.decide_reservation(
                        st.session_state.admin_auth_session_id, action_id, "reject"
                    )
                    st.toast("예약을 거절했습니다.", icon=":material/cancel:")
                    st.rerun()
                except AgentClientError as error:
                    st.error(str(error), icon=":material/error:")
