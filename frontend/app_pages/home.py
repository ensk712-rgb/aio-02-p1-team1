"""시안 기반 통합 홈 대시보드."""

import streamlit as st

from frontend.bootstrap import get_client, logout, reset_conversation
from frontend.components.chat_panel import render_chat_panel
from frontend.components.dashboard import (
    current_time_label,
    render_animal_card,
    render_crowding_card,
    render_feeding_card,
    render_hero,
    render_route_card,
)
from frontend.components.layout import render_sidebar

from frontend.components.reservation import render_reservation


client = get_client()
render_sidebar("home")

header_left, header_right = st.columns([4, 1], vertical_alignment="center")
with header_left:
    st.markdown("## 우리동물원 AI 가이드 🌿")
    st.caption("자연과 동물이 함께하는 특별한 하루 되세요!")
with header_right:
    st.caption(f":material/schedule: {current_time_label()} · {st.session_state.user_id}")
    with st.container(horizontal=True, horizontal_alignment="right"):
        st.button("새 대화", icon=":material/refresh:", on_click=reset_conversation, key="new_conversation")
        st.button("로그아웃", icon=":material/logout:", on_click=logout, key="logout")

render_hero()
with st.form("hero_question_form", border=False):
    question = st.text_input(
        "AI에게 물어보기",
        placeholder="예: 판다는 어디에 있어?",
        label_visibility="collapsed",
        key="hero_question",
        max_chars=2000,
    )
    hero_submitted = st.form_submit_button(
        "AI에게 질문하기",
        icon=":material/arrow_forward:",
        disabled=st.session_state.get("chat_status") == "processing",
    )

if hero_submitted and question.strip():
    st.session_state.pending_question = question.strip()
    st.rerun()

render_chat_panel(client)

quick_columns = st.columns(3)
quick_questions = (
    ("인기 동물은?", "판다는 어디에서 무엇을 먹어?"),
    ("오늘의 먹이주기", "해양관 펭귄 먹이시간을 알려줘"),
    ("추천 관람 동선", "정문에서 해양관까지 가는 경로를 알려줘"),
)
for column, (label, prompt) in zip(quick_columns, quick_questions):
    with column:
        if st.button(label, width="stretch", key=f"quick_{label}"):
            st.session_state.pending_question = prompt
            st.rerun()

cards = st.columns(4)
with cards[0]:
    render_feeding_card()
with cards[1]:
    render_route_card()
with cards[2]:
    render_animal_card()
with cards[3]:
    render_crowding_card()
