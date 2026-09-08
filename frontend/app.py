"""Zoo Visit Guide 사용자 앱 진입점: 인증, 공통 상태, 내비게이션."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT_PATH = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT_PATH) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_PATH))

import streamlit as st

from frontend.bootstrap import get_client, initialize_state
from frontend.clients.agent_client import AgentClientError
from frontend.styles import apply_theme

st.set_page_config(page_title="우리동물원 AI 가이드", page_icon=":material/pets:", layout="wide", initial_sidebar_state="expanded")
apply_theme()
initialize_state()
client = get_client()

if not st.session_state.login_success:
    _, login_column, _ = st.columns([1, 1.15, 1], vertical_alignment="center")
    with login_column:
        with st.container(border=True, key="login_card"):
            st.title("우리동물원", icon=":material/pets:")
            st.subheader("AI 가이드 로그인")
            st.caption("등록된 관람 계정으로 오늘의 안내를 시작하세요.")
            with st.form("user_login"):
                user_id = st.text_input("아이디", key="login_user_id")
                password = st.text_input("비밀번호", type="password", key="login_password")
                submitted = st.form_submit_button("로그인", icon=":material/login:", width="stretch")
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
navigation = st.navigation(
    [
        st.Page("app_pages/home.py", title="홈", icon=":material/home:", default=True),
        st.Page("app_pages/animal_info.py", title="동물 정보", icon=":material/pets:"),
        st.Page("app_pages/zoo_map.py", title="지도", icon=":material/map:"),
        st.Page("app_pages/feeding_schedule.py", title="먹이주기 일정", icon=":material/calendar_month:"),
        st.Page("app_pages/reservation.py", title="체험 예약", icon=":material/confirmation_number:"),
        st.Page("app_pages/route_recommendation.py", title="관람 동선 추천", icon=":material/route:"),
        st.Page("app_pages/environment.py", title="환경 상태", icon=":material/device_thermostat:"),
    ],
    position="hidden",
)
navigation.run()
