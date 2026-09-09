"""예약 승인 전용 Streamlit 관리자 화면."""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT_PATH = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT_PATH) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_PATH))

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

st.html("""
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css');
:root { --ink-panel:#0e2a21; --ink-panel-2:#163b30; --leaf-bright:#9fd7b4; --moss-soft:#e6f2ec; --sand:#e1e9e4; }
html, body, [data-testid="stAppViewContainer"] { font-family:"Pretendard Variable",Pretendard,-apple-system,BlinkMacSystemFont,"Noto Sans KR","Malgun Gothic",sans-serif; }
[data-testid="stAppViewContainer"] { background:linear-gradient(135deg,#f3f7f4,var(--moss-soft)); }
[data-testid="stHeader"] { background:transparent; }
.block-container { max-width:1280px; padding-top:1.4rem; }
.admin-hero { padding:32px 38px; border-radius:14px; color:white; background:radial-gradient(circle at 85% 20%,rgba(159,215,180,.32),transparent 28%),linear-gradient(105deg,var(--ink-panel),var(--ink-panel-2)); box-shadow:0 18px 45px rgba(14,42,33,.20); }
.admin-hero h1 { margin:.2rem 0; }
div[data-testid="stVerticalBlockBorderWrapper"] { border-color:var(--sand); box-shadow:0 10px 26px rgba(14,42,33,.07); }
</style>
""")


@st.cache_resource
def get_client():
    if os.getenv("ZOO_UI_FAKE_MODE") == "1":
        return FakeAgentClient()
    return AgentClient(os.getenv("BACKEND_URL", "http://127.0.0.1:8000"))


def initialize_state() -> None:
    st.session_state.setdefault("admin_login_success", False)
    st.session_state.setdefault("admin_user_id", None)
    st.session_state.setdefault("admin_auth_session_id", None)
    st.session_state.setdefault("admin_processing_action", None)
    st.session_state.setdefault("admin_notice", None)
    st.session_state.setdefault("admin_trace_result", None)


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
    st.session_state.admin_processing_action = None
    st.session_state.admin_notice = None
    st.session_state.admin_trace_result = None


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
            if result.get("role") != "admin":
                raise AgentClientError("관리자 권한이 있는 계정만 접근할 수 있습니다.", kind="http")
            st.session_state.admin_login_success = result.get("success") is True
            st.session_state.admin_user_id = result.get("user_id")
            st.session_state.admin_auth_session_id = result.get("auth_session_id")
            st.rerun()
        except AgentClientError as error:
            st.error(str(error), icon=":material/error:")
    st.stop()

st.session_state.pop("admin_login_password", None)
st.session_state.pop("admin_login_user_id", None)

st.html('<section class="admin-hero"><div>RESERVATION CONTROL</div><h1>예약 승인 안내소</h1><p>관람객이 직접 확인한 요청만 안전하게 검토합니다.</p></section>')
with st.container(horizontal=True, horizontal_alignment="right"):
    st.button("새로고침", icon=":material/refresh:", key="admin_refresh")
    st.button("로그아웃", icon=":material/logout:", on_click=logout, key="admin_logout")

st.caption(f"담당 계정 · {st.session_state.admin_user_id}")

with st.container(border=True):
    st.subheader("MCP 도구 상태", icon=":material/hub:")
    try:
        health = client.get_health()
        connected = health.get("status") == "ok" and health.get("mcp") == "ok"
        status_columns = st.columns(4)
        status_columns[0].metric("전체 상태", "정상" if connected else "확인 필요")
        status_columns[1].metric("Backend", str(health.get("backend", "unknown")))
        status_columns[2].metric("MCP", str(health.get("mcp", "unknown")))
        status_columns[3].metric("실행 모드", str(health.get("app_mode", "unknown")))
        if connected:
            st.success("동물 정보·지도·먹이주기 도구가 연결되어 있습니다.", icon=":material/check_circle:")
        else:
            st.warning("일부 도구 연결을 확인해 주세요.", icon=":material/warning:")
    except AgentClientError as error:
        st.error(str(error), icon=":material/cloud_off:")

notice = st.session_state.get("admin_notice")
if isinstance(notice, dict):
    if notice.get("level") == "error":
        st.error(str(notice.get("message")), icon=":material/error:")
    else:
        st.success(str(notice.get("message")), icon=":material/check_circle:")
    st.session_state.admin_notice = None

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
            processing = st.session_state.admin_processing_action is not None
            if st.button("승인", type="primary", icon=":material/check:", disabled=processing, key=f"approve_{action_id}"):
                st.session_state.admin_processing_action = action_id
                try:
                    client.decide_reservation(
                        st.session_state.admin_auth_session_id, action_id, "approve"
                    )
                    st.session_state.admin_notice = {"level": "success", "message": "예약을 승인했습니다."}
                except AgentClientError as error:
                    st.session_state.admin_notice = {"level": "error", "message": str(error)}
                finally:
                    st.session_state.admin_processing_action = None
                st.rerun()
            if st.button("거절", icon=":material/close:", disabled=processing, key=f"reject_{action_id}"):
                st.session_state.admin_processing_action = action_id
                try:
                    client.decide_reservation(
                        st.session_state.admin_auth_session_id, action_id, "reject"
                    )
                    st.session_state.admin_notice = {"level": "success", "message": "예약을 거절했습니다."}
                except AgentClientError as error:
                    st.session_state.admin_notice = {"level": "error", "message": str(error)}
                finally:
                    st.session_state.admin_processing_action = None
                st.rerun()

st.divider()
st.subheader("Agent 실행 Trace", icon=":material/monitoring:")
st.caption("사용자 화면의 Agent 세션 ID로 최근 실행 상태와 Tool 처리 내역을 조회합니다.")
with st.form("admin_trace_search"):
    trace_session_id = st.text_input(
        "Agent 세션 ID",
        placeholder="예: guest-...",
        key="admin_trace_session_id",
    )
    trace_submitted = st.form_submit_button(
        "Trace 조회", icon=":material/search:", width="stretch"
    )

if trace_submitted:
    if not trace_session_id.strip():
        st.warning("조회할 Agent 세션 ID를 입력해 주세요.", icon=":material/warning:")
    else:
        try:
            st.session_state.admin_trace_result = client.get_admin_trace(
                st.session_state.admin_auth_session_id,
                trace_session_id.strip(),
            )
        except AgentClientError as error:
            st.error(str(error), icon=":material/error:")

trace_result = st.session_state.get("admin_trace_result")
if isinstance(trace_result, dict):
    runs = trace_result.get("runs", [])
    if not runs:
        st.info("해당 세션의 Trace가 없습니다.", icon=":material/info:")
    for run in reversed(runs):
        run_id = str(run.get("run_id", "run"))
        status_value = str(run.get("status", "unknown"))
        with st.expander(f"{run_id} · {status_value}", expanded=True):
            trace = run.get("trace", [])
            if trace:
                st.json(trace, expanded=1)
            else:
                st.caption("기록된 세부 이벤트가 없습니다.")
