"""예약 승인 전용 Streamlit 관리자 화면."""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

PROJECT_ROOT_PATH = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT_PATH) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_PATH))

import streamlit as st
from dotenv import load_dotenv

from frontend.clients.agent_client import AgentClient, AgentClientError
from frontend.clients.fake_agent_client import FakeAgentClient


FRONTEND_ROOT = PROJECT_ROOT_PATH / "frontend"
load_dotenv(FRONTEND_ROOT / ".env")

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
    return AgentClient(os.getenv("BACKEND_URL", "http://192.100.200.198:8000/"))


def initialize_state() -> None:
    st.session_state.setdefault("admin_login_success", False)
    st.session_state.setdefault("admin_user_id", None)
    st.session_state.setdefault("admin_auth_session_id", None)
    st.session_state.setdefault("admin_processing_action", None)
    st.session_state.setdefault("admin_notice", None)
    st.session_state.setdefault("admin_trace_result", None)
    st.session_state.setdefault("admin_trace_session_id", None)


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
    st.session_state.admin_trace_session_id = None


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

def _format_time(value: object) -> str:
    """UTC 저장 시각을 관리자 화면에서 KST로 표시한다."""
    if not isinstance(value, str):
        return "시각 정보 없음"
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    return moment.astimezone(ZoneInfo("Asia/Seoul")).strftime("%m-%d %H:%M")


def _redact(value: Any, key: str = "") -> Any:
    """상세 화면의 예약·인증 관련 값을 마스킹한다."""
    secret_keys = {"headcount", "visit_time", "user_id", "session_id", "authorization", "token"}
    if key.lower() in secret_keys:
        return "***"
    if isinstance(value, dict):
        return {item_key: _redact(item_value, item_key) for item_key, item_value in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _status_label(status_value: str) -> str:
    labels = {
        "completed": "완료",
        "error": "오류",
        "rejected": "차단",
        "stopped": "중단",
        "needs_clarification": "추가 정보 필요",
        "confirmation_required": "사용자 확인 대기",
    }
    return labels.get(status_value, status_value)


st.divider()
st.subheader("Agent 실행 Trace", icon=":material/monitoring:")
st.caption("최근 24시간의 실행 세션을 선택하면 상세 Trace를 확인할 수 있습니다. 질문과 예약 정보는 마스킹됩니다.")

try:
    trace_sessions = client.list_admin_trace_sessions(st.session_state.admin_auth_session_id).get("sessions", [])
except AgentClientError as error:
    trace_sessions = []
    st.error(str(error), icon=":material/error:")

header, refresh_column = st.columns([5, 1], vertical_alignment="bottom")
with header:
    st.caption(f"최근 세션 {len(trace_sessions)}개 · 상세 Trace는 실행 후 2시간까지 보관됩니다.")
with refresh_column:
    if st.button("새로고침", icon=":material/refresh:", key="admin_trace_refresh", width="stretch"):
        st.rerun()

if not trace_sessions:
    st.info("최근 24시간에 실행된 Agent 세션이 없습니다.", icon=":material/inbox:")
else:
    session_lookup = {str(item["session_id"]): item for item in trace_sessions}
    options = list(session_lookup)
    selected_session = st.selectbox(
        "최근 Agent 세션",
        options,
        key="admin_trace_session_id",
        format_func=lambda session_id: (
            f"[{_status_label(str(session_lookup[session_id].get('status', 'unknown')))}] "
            f"{_format_time(session_lookup[session_id].get('last_run_at'))} · "
            f"{session_lookup[session_id].get('question_preview', '질문 내용 없음')}"
        ),
    )
    if selected_session not in session_lookup:
        selected_session = options[0]
    selected_summary = session_lookup[selected_session]
    tools = selected_summary.get("tools") or []
    st.caption(f"Tool: {', '.join(map(str, tools)) if tools else '호출 없음'}")

    try:
        st.session_state.admin_trace_result = client.get_admin_trace(
            st.session_state.admin_auth_session_id, selected_session
        )
    except AgentClientError as error:
        st.session_state.admin_trace_result = None
        st.error(str(error), icon=":material/error:")

trace_result = st.session_state.get("admin_trace_result")
if isinstance(trace_result, dict):
    runs = trace_result.get("runs", [])
    if trace_result.get("detail_expired"):
        st.info("상세 실행 기록이 만료되었습니다. 목록 요약은 24시간 동안 유지됩니다.", icon=":material/schedule:")
    elif not runs:
        st.info("기록된 상세 Trace가 없습니다.", icon=":material/info:")
    else:
        latest = runs[-1]
        all_tools = {
            str(item.get("data", {}).get("tool"))
            for run in runs
            for item in run.get("trace", [])
            if isinstance(item, dict) and isinstance(item.get("data"), dict) and item["data"].get("tool")
        }
        summary_columns = st.columns(4)
        summary_columns[0].metric("최종 상태", _status_label(str(latest.get("status", "unknown"))))
        summary_columns[1].metric("실행 횟수", len(runs))
        summary_columns[2].metric("호출 Tool", len(all_tools))
        summary_columns[3].metric("종료 사유", str(next((item.get("data", {}).get("reason") for item in latest.get("trace", []) if isinstance(item, dict) and item.get("stage") == "run_finished"), "-")))

        for run in reversed(runs):
            run_id = str(run.get("run_id", "run"))
            status_value = str(run.get("status", "unknown"))
            with st.expander(f"{run_id} · {_status_label(status_value)}", expanded=True):
                trace = run.get("trace", [])
                if trace:
                    for item in trace:
                        if not isinstance(item, dict):
                            continue
                        stage = str(item.get("stage") or item.get("event") or "event")
                        owner = str(item.get("owner", "runtime"))
                        data = _redact(item.get("data", {}))
                        st.markdown(f"**{owner}** · `{stage}`")
                        if data:
                            st.json(data, expanded=False)
                    with st.expander("원본 Trace JSON (마스킹됨)", expanded=False):
                        st.json(_redact(trace), expanded=False)
                else:
                    st.caption("기록된 세부 이벤트가 없습니다.")
