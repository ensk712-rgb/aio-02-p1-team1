"""시안 기반 통합 홈 대시보드."""

import streamlit as st

from frontend.bootstrap import get_client, logout, reset_conversation
from frontend.components.chat_panel import render_chat_panel
from frontend.components.dashboard import current_time_label, render_animal_card, render_feeding_card, render_hero, render_route_card
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

main, rail = st.columns([3.35, 1.05], gap="large")
with main:
    render_hero()
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

    cards = st.columns(3)
    with cards[0]: render_feeding_card()
    with cards[1]: render_route_card()
    with cards[2]: render_animal_card()
    render_reservation(client)

with rail:
    with st.container(border=True):
        st.subheader("실시간 혼잡도", icon=":material/groups:")
        st.progress(0.43, text="보통")
        st.caption("오전 시간대에는 여유롭게 관람할 수 있어요. · 시연용 Mock")
