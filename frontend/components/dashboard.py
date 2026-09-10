"""홈 대시보드의 표시 전용 컴포넌트."""

import base64
from datetime import datetime
from pathlib import Path
import streamlit as st


def render_hero() -> None:
    image_path = Path(__file__).resolve().parents[1] / "image" / "예약승인 팜플릿 이미지.png"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    st.html(f"""<section class="zoo-hero" style="background-image:url(data:image/png;base64,{encoded})" aria-label="우리동물원 AI 가이드 소개"><div class="zoo-kicker" style="color:var(--leaf-bright)">WELCOME TO OUR ZOO</div><h1>오늘 어떤 동물을<br>만나볼까요?</h1><p>궁금한 동물과 먹이시간, 휴장 정보, 관람 경로를 AI 가이드에게 물어보세요.</p></section>""")


def render_feeding_card() -> None:
    with st.container(border=True, height="stretch"):
        st.subheader("먹이주기 일정", icon=":material/calendar_month:")
        st.caption("시연용 Mock · 현장 상황에 따라 변경될 수 있습니다.")
        st.table({"시간":["10:30","11:00","13:30","15:30"],"동물":["기린","펭귄","코끼리","호랑이"],"장소":["사바나","펭귄 빌리지","코끼리 숲","호랑이 숲"]}, border="horizontal")


def render_route_card() -> None:
    with st.container(border=True, height="stretch"):
        st.subheader("추천 관람 동선", icon=":material/route:")
        st.html('<div class="zoo-route">입구 → 🦒 사바나<br>↘ 🐼 판다월드 ↙<br>🐧 펭귄 빌리지</div>')
        st.caption("약 2시간 30분 · 약 3.2km · 시연용 Mock")


def render_animal_card() -> None:
    with st.container(border=True, height="stretch"):
        st.subheader("동물 백과", icon=":material/menu_book:")
        st.html('<div class="zoo-route" style="font-size:4rem;line-height:1.8">🐼</div>')
        st.markdown("**자이언트 판다** :green-badge[포유류]")
        st.caption("대나무를 주식으로 하는 중국의 국보급 동물이에요.")


def render_crowding_card() -> None:
    with st.container(border=True, height="stretch"):
        st.subheader("실시간 혼잡도", icon=":material/groups:")
        st.progress(0.43, text="보통")
        st.caption("오전 시간대에는 여유롭게 관람할 수 있어요.")
        st.caption("시연용 Mock · 현장 상황에 따라 달라질 수 있습니다.")


def current_time_label() -> str:
    return datetime.now().astimezone().strftime("%H:%M")
