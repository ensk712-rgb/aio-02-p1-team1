"""모든 사용자 페이지가 공유하는 내비게이션과 시각 헤더."""

from __future__ import annotations

import base64
import html
import mimetypes
from pathlib import Path

import streamlit as st

from frontend.bootstrap import logout

IMAGE_DIR = Path(__file__).resolve().parents[1] / "image"


def render_sidebar(active: str) -> None:
    with st.sidebar:
        st.html('<div class="zoo-brand">🐾 우리동물원<br>AI 가이드</div>')
        st.caption("자연과 동물이 함께하는 특별한 하루")
        st.space("small")
        links = (
            ("app_pages/home.py", "홈", ":material/home:"),
            ("app_pages/animal_info.py", "동물 정보", ":material/pets:"),
            ("app_pages/feeding_schedule.py", "먹이주기 일정", ":material/calendar_month:"),
            ("app_pages/reservation.py", "체험 예약", ":material/confirmation_number:"),
            ("app_pages/route_recommendation.py", "관람 동선 추천", ":material/route:"),
            ("app_pages/environment.py", "날씨 정보", ":material/cloud:"),
            ("app_pages/voice_assistant.py", "음성 안내", ":material/mic:"),
            ("app_pages/image_analysis.py", "이미지 분석", ":material/image_search:"),
            ("app_pages/notice.py", "안내 및 주의사항", ":material/info:"),
            ("app_pages/refund.py", "취소 및 환불", ":material/receipt_long:"),
        )
        for path, label, icon in links:
            st.page_link(path, label=label, icon=icon, width="stretch")
        st.space("large")
        with st.container(border=True):
            st.markdown("**오늘의 한마디**")
            st.write("동물에게 조용한 응원과 따뜻한 시선을 보내주세요.")
        st.caption(f"접속 계정 · {st.session_state.user_id}")
        st.button("로그아웃", icon=":material/logout:", on_click=logout, width="stretch", key=f"logout_{active}")


def render_page_hero(title: str, subtitle: str, image_name: str, eyebrow: str) -> None:
    path = IMAGE_DIR / image_name
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    st.html(
        f'<section class="zoo-page-hero" style="background-image:url(data:{mime};base64,{encoded})">'
        f'<div class="zoo-kicker" style="color:var(--leaf-bright)">{html.escape(eyebrow)}</div>'
        f'<h1>{html.escape(title)}</h1><p>{html.escape(subtitle)}</p></section>'
    )


def render_mock_notice() -> None:
    st.caption(":material/science: 현재 화면의 일정·혼잡도·환경 수치는 기능 시연용 Mock 데이터입니다.")
