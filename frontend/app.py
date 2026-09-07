"""Zoo Visit Guide 단일 Streamlit 화면."""

from __future__ import annotations

import os
from typing import Any, Protocol

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from backend.app.core.config import PROJECT_ROOT
from frontend.clients.agent_client import AgentClient, AgentClientError
from frontend.clients.fake_agent_client import FakeAgentClient
from frontend.ui import render_agent_response


class AgentClientProtocol(Protocol):
    def get_health(self) -> dict[str, Any]: ...
    def ask(self, message: str, session_id: str | None = None) -> dict[str, Any]: ...
    def login(self, user_id: str, password: str) -> dict[str, Any]: ...
    def logout(self, auth_session_id: str) -> None: ...
    def create_reservation(self, auth_session_id: str, **payload: Any) -> dict[str, Any]: ...
    def confirm_reservation(
        self, auth_session_id: str, action_id: str, decision: str
    ) -> dict[str, Any]: ...
    def get_my_reservations(self, auth_session_id: str) -> dict[str, Any]: ...


load_dotenv(PROJECT_ROOT / ".env")

st.set_page_config(
    page_title="Zoo Visit Guide",
    page_icon=":material/pets:",
    layout="centered",
)


@st.cache_resource
def get_client() -> AgentClientProtocol:
    if os.getenv("ZOO_UI_FAKE_MODE") == "1":
        return FakeAgentClient()
    return AgentClient(os.getenv("BACKEND_URL", "http://127.0.0.1:8000"))


def initialize_state() -> None:
    st.session_state.setdefault("session_id", None)
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("login_success", False)
    st.session_state.setdefault("user_id", None)
    st.session_state.setdefault("auth_session_id", None)
    st.session_state.setdefault("pending_reservation_action", None)
    st.session_state.setdefault("approval_processing", False)
    st.session_state.setdefault("approval_notice", None)


def reset_conversation() -> None:
    st.session_state.session_id = None
    st.session_state.messages = []


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
    reset_conversation()


initialize_state()
client = get_client()

if not st.session_state.login_success:
    st.title("동물원 관람 로그인", icon=":material/login:")
    st.caption("등록된 관람 계정으로 로그인해 주세요.")
    with st.form("user_login"):
        user_id = st.text_input("아이디", key="login_user_id")
        password = st.text_input("비밀번호", type="password", key="login_password")
        submitted = st.form_submit_button("로그인", icon=":material/login:")
    if submitted:
        try:
            result = client.login(user_id, password)
            st.session_state.login_success = result.get("success") is True
            st.session_state.user_id = result.get("user_id")
            st.session_state.auth_session_id = result.get("auth_session_id")
            st.rerun()
        except AgentClientError as error:
            st.error(str(error), icon=":material/error:")
    st.stop()

st.session_state.pop("login_password", None)
st.session_state.pop("login_user_id", None)

with st.container(horizontal=True, vertical_alignment="center"):
    st.title("오늘의 동물원 길잡이", icon=":material/pets:")
    st.button(
        "새 대화",
        icon=":material/refresh:",
        on_click=reset_conversation,
        key="new_conversation",
    )
    st.button("로그아웃", icon=":material/logout:", on_click=logout, key="logout")

st.caption("동물 정보와 먹이시간·휴장·관람 경로를 확인해 드립니다.")
st.info(
    "운영 정보는 교육용 Mock 데이터입니다. 현장 안내판도 함께 확인해 주세요.",
    icon=":material/info:",
)

with st.expander("체험 예약 요청", icon=":material/event:"):
    with st.form("reservation_request"):
        program = st.selectbox("프로그램", ["사육사 체험", "먹이주기 체험"], key="program")
        visit_time = st.selectbox("시간", ["11:00", "15:00"], key="visit_time")
        headcount = st.number_input("인원", min_value=1, max_value=10, value=1, key="headcount")
        reserve_submitted = st.form_submit_button("승인 요청", icon=":material/send:")
    if reserve_submitted:
        try:
            result = client.create_reservation(
                st.session_state.auth_session_id,
                program=program,
                visit_time=visit_time,
                headcount=int(headcount),
            )
            st.session_state.pending_reservation_action = result.get("pending_action")
            st.session_state.approval_notice = result.get("message")
        except AgentClientError as error:
            st.error(str(error), icon=":material/error:")

    notice = st.session_state.get("approval_notice")
    if notice:
        st.info(str(notice), icon=":material/info:")
        st.session_state.approval_notice = None

    pending_action = st.session_state.get("pending_reservation_action")
    if isinstance(pending_action, dict):
        action_id = str(pending_action.get("action_id", ""))
        with st.container(border=True, key=f"approval_card_{action_id}"):
            st.subheader("예약 내용을 확인해 주세요", icon=":material/verified_user:")
            st.write(str(pending_action.get("summary", "예약 요청")))
            st.caption(f"확인 만료 시각 · {pending_action.get('expires_at', '확인 불가')}")
            with st.container(horizontal=True):
                confirm_clicked = st.button(
                    "확인",
                    type="primary",
                    icon=":material/check:",
                    disabled=st.session_state.approval_processing,
                    key=f"confirm_{action_id}",
                )
                cancel_clicked = st.button(
                    "취소",
                    icon=":material/close:",
                    disabled=st.session_state.approval_processing,
                    key=f"cancel_{action_id}",
                )
            if confirm_clicked or cancel_clicked:
                st.session_state.approval_processing = True
                try:
                    result = client.confirm_reservation(
                        st.session_state.auth_session_id,
                        action_id,
                        "confirm" if confirm_clicked else "cancel",
                    )
                    st.session_state.pending_reservation_action = None
                    st.session_state.approval_notice = result.get("message")
                except AgentClientError as error:
                    st.session_state.pending_reservation_action = None
                    st.session_state.approval_notice = str(error)
                finally:
                    st.session_state.approval_processing = False
                st.rerun()

    try:
        reservation_items = client.get_my_reservations(st.session_state.auth_session_id).get("items", [])
        if reservation_items:
            st.dataframe(
                pd.DataFrame(reservation_items)[["program", "visit_time", "headcount", "status"]],
                hide_index=True,
                key="my_reservations",
            )
    except AgentClientError:
        st.warning("예약 현황을 불러올 수 없습니다.", icon=":material/warning:")

try:
    health = client.get_health()
    mcp_status = health.get("mcp", "unavailable")
    if health.get("status") != "ok" or mcp_status != "ok":
        st.warning("현재 일부 운영 정보를 확인할 수 없습니다.", icon=":material/warning:")
except AgentClientError:
    st.warning("안내 서버 상태를 확인할 수 없습니다.", icon=":material/cloud_off:")

if not st.session_state.messages:
    with st.container(border=True):
        st.subheader("관람 체크포인트", icon=":material/signpost:")
        st.markdown(
            "- 펭귄은 언제 먹이를 먹나요?\n"
            "- 오늘 쉬는 전시관이 있나요?\n"
            "- 정문에서 해양관까지 어떻게 가나요?"
        )

for msg_index, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            render_agent_response(message["response"], key_prefix=f"history_{msg_index}")
        else:
            st.markdown(message["content"])

question = st.chat_input("동물, 먹이시간, 휴장 또는 경로를 물어보세요", key="question")
if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        try:
            with st.spinner("안내 지도를 확인하고 있습니다…"):
                response = client.ask(question, st.session_state.session_id)
            session_id = response.get("session_id")
            if isinstance(session_id, str) and session_id:
                st.session_state.session_id = session_id
            st.session_state.messages.append(
                {"role": "assistant", "response": response}
            )
            render_agent_response(
                response, key_prefix=f"history_{len(st.session_state.messages) - 1}"
            )
        except AgentClientError as error:
            st.error(str(error), icon=":material/error:")
